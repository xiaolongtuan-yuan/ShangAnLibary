"""个人资料相关请求模型（契约 §4.1）。"""

from pydantic import BaseModel


class UpdateMeRequest(BaseModel):
    username: str | None = None
    email: str | None = None


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str
