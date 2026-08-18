"""认证相关请求/响应模型（契约 §4.1）。"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    invite_code: str


class LoginRequest(BaseModel):
    username: str  # 用户名或邮箱
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserBrief(ORMModel):
    id: int
    username: str
    email: str
    role: str


class UserOut(UserBrief):
    created_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserBrief


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
