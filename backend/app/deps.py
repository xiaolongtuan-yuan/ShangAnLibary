"""依赖：get_db / get_current_user / require_admin。"""

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """解析 Bearer access token → 查用户 → status 校验，失败一律 401。"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="登录状态无效，请重新登录")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在或已被删除")
    if user.status != "normal":
        raise HTTPException(status_code=401, detail="账号已被禁用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """管理员专用接口依赖：非 admin 一律 403。"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    return user
