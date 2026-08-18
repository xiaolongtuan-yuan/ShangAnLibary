"""个人资料接口（契约 §4.1）：改资料 / 改密码。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.auth import UserOut
from app.schemas.user import PasswordChangeRequest, UpdateMeRequest
from app.services.security import hash_password, verify_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
def update_me(
    body: UpdateMeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改本人资料（用户名/邮箱均可选）。"""
    if body.username is not None:
        username = body.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="用户名不能为空")
        if len(username) > 32:
            raise HTTPException(status_code=400, detail="用户名最长 32 个字符")
        dup = db.query(User).filter(User.username == username, User.id != user.id).first()
        if dup:
            raise HTTPException(status_code=400, detail="用户名已被使用")
        user.username = username
    if body.email is not None:
        email = body.email.strip()
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="邮箱格式不正确")
        dup = db.query(User).filter(User.email == email, User.id != user.id).first()
        if dup:
            raise HTTPException(status_code=400, detail="邮箱已被使用")
        user.email = email
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.put("/me/password")
def change_password(
    body: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改密码：需校验原密码。"""
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "密码已修改"}
