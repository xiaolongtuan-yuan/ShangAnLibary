"""认证接口（契约 §4.1）：注册（邀请码）、登录（限流）、refresh（轮换）、me。"""

import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import InviteCode, User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    TokenResponse,
    UserBrief,
    UserOut,
)
from app.services.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_refresh_revoked,
    revoke_refresh_token,
    verify_password,
)
from app.utils import to_naive, utcnow

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 60
_login_attempts: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    """优先取 X-Forwarded-For（Nginx 反代场景），否则取直连 IP。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_login_rate_limit(ip: str) -> None:
    """内存限流：5 次/分钟/IP，超限抛 429。"""
    now = time.time()
    recent = [t for t in _login_attempts.get(ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    if len(recent) >= LOGIN_LIMIT:
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请 1 分钟后再试")
    recent.append(now)
    _login_attempts[ip] = recent


@router.post("/register", status_code=201, response_model=UserBrief)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """邀请码注册：校验邀请码有效性，成功后 used_count + 1。"""
    username = body.username.strip()
    email = body.email.strip()
    if not username or not email:
        raise HTTPException(status_code=400, detail="用户名和邮箱不能为空")
    if len(username) > 32:
        raise HTTPException(status_code=400, detail="用户名最长 32 个字符")
    if "@" not in email or len(email) > 255:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少 8 位")

    exists = db.query(User).filter((User.username == username) | (User.email == email)).first()
    if exists:
        raise HTTPException(status_code=400, detail="用户名或邮箱已被注册")

    code = db.query(InviteCode).filter(InviteCode.code == body.invite_code.strip()).first()
    if code is None or code.revoked:
        raise HTTPException(status_code=400, detail="邀请码无效")
    if code.used_count >= code.max_uses:
        raise HTTPException(status_code=400, detail="邀请码已被使用完")
    expires = to_naive(code.expires_at)
    if expires is not None and expires < utcnow():
        raise HTTPException(status_code=400, detail="邀请码已过期")

    user = User(username=username, email=email, password_hash=hash_password(body.password), role="user")
    db.add(user)
    code.used_count += 1
    db.commit()
    db.refresh(user)
    return UserBrief.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """登录（username 可为用户名或邮箱）；被禁用账号返回 403。"""
    _check_login_rate_limit(_client_ip(request))
    user = (
        db.query(User)
        .filter((User.username == body.username) | (User.email == body.username))
        .first()
    )
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user.status != "normal":
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role),
        user=UserBrief.model_validate(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """刷新 access token；旧 refresh 立即失效（轮换）。"""
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="刷新令牌无效或已过期")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="刷新令牌无效")
    jti = payload.get("jti")
    if not jti or is_refresh_revoked(jti):
        raise HTTPException(status_code=401, detail="刷新令牌已失效，请重新登录")
    sub = payload.get("sub")
    try:
        user = db.get(User, int(sub)) if sub else None
    except (TypeError, ValueError):
        user = None
    if user is None or user.status != "normal":
        raise HTTPException(status_code=401, detail="用户不存在或已被禁用")
    revoke_refresh_token(jti)
    return RefreshResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)
