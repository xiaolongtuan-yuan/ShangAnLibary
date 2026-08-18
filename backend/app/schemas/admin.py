"""管理后台模型（契约 §4.9）。"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class AdminUserOut(ORMModel):
    id: int
    username: str
    email: str
    role: str
    status: str
    created_at: datetime


class AdminUserUpdate(BaseModel):
    status: str | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


class InviteCodeGenerate(BaseModel):
    count: int = 1
    max_uses: int = 1
    expires_days: int | None = None


class InviteCodeGenerateResult(BaseModel):
    codes: list[str]


class InviteCodeOut(ORMModel):
    id: int
    code: str
    max_uses: int
    used_count: int
    expires_at: datetime | None = None
    revoked: bool
    created_at: datetime


class StatsOut(BaseModel):
    users: int
    documents: int
    folders: int
    annotations: int
    total_file_size: int
