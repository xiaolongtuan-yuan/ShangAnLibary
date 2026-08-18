"""安全服务：argon2 密码哈希、PyJWT 签发/校验、签名文件 URL。"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import settings

_hasher = PasswordHasher()

# 内存中的已轮换 refresh token jti 黑名单（重启即失效，MVP 可接受）
_revoked_refresh_jtis: set[str] = set()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def create_token(
    user_id: int, role: str, token_type: str, expires_delta: timedelta, jti: str | None = None
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if jti:
        payload["jti"] = jti
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_access_token(user_id: int, role: str) -> str:
    return create_token(
        user_id, role, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: int, role: str) -> str:
    return create_token(
        user_id,
        role,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        jti=secrets.token_hex(16),
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])


def revoke_refresh_token(jti: str) -> None:
    """refresh 轮换时把旧令牌 jti 加入黑名单，使其立即失效。"""
    _revoked_refresh_jtis.add(jti)


def is_refresh_revoked(jti: str) -> bool:
    return jti in _revoked_refresh_jtis


def _file_signature(doc_id: int, exp: int) -> str:
    message = f"doc:{doc_id}:{exp}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()


def make_file_url(doc_id: int, ttl: int = 300) -> str:
    """生成短时效（默认 5 分钟）的相对签名 URL。"""
    exp = _now_ts() + ttl
    return f"/api/files/stream/{doc_id}?exp={exp}&sig={_file_signature(doc_id, exp)}"


def verify_file_signature(doc_id: int, exp: int, sig: str) -> bool:
    """校验签名与过期时间；任一失败返回 False。"""
    if not sig or _now_ts() > exp:
        return False
    expected = _file_signature(doc_id, exp)
    return hmac.compare_digest(expected, sig)
