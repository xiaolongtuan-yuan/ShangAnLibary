"""管理后台接口（契约 §4.9）：用户管理 / 邀请码 / 统计，全部仅管理员。"""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Annotation, Document, Folder, InviteCode, User
from app.schemas.admin import (
    AdminUserOut,
    AdminUserUpdate,
    InviteCodeGenerate,
    InviteCodeGenerateResult,
    InviteCodeOut,
    ResetPasswordRequest,
    StatsOut,
)
from app.services.security import hash_password
from app.utils import utcnow

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserOut])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id.asc()).all()
    return [AdminUserOut.model_validate(u) for u in users]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """禁用 / 启用用户。"""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if body.status is not None:
        if body.status not in ("normal", "disabled"):
            raise HTTPException(status_code=400, detail="status 只能是 normal 或 disabled")
        if target.id == admin.id and body.status == "disabled":
            raise HTTPException(status_code=400, detail="不能禁用当前登录的管理员账号")
        target.status = body.status
    db.commit()
    db.refresh(target)
    return AdminUserOut.model_validate(target)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    target.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "已重置"}


@router.post("/invite-codes", status_code=201, response_model=InviteCodeGenerateResult)
def generate_invite_codes(
    body: InviteCodeGenerate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批量生成邀请码（secrets.token_urlsafe(6).upper() 风格）。"""
    count = max(1, min(body.count or 1, 100))
    max_uses = max(1, body.max_uses or 1)
    expires_at = utcnow() + timedelta(days=body.expires_days) if body.expires_days else None
    codes: list[str] = []
    for _ in range(count):
        code = secrets.token_urlsafe(6).upper()
        while db.query(InviteCode).filter(InviteCode.code == code).first():
            code = secrets.token_urlsafe(6).upper()
        db.add(InviteCode(code=code, max_uses=max_uses, expires_at=expires_at, created_by=admin.id))
        codes.append(code)
    db.commit()
    return InviteCodeGenerateResult(codes=codes)


@router.get("/invite-codes", response_model=list[InviteCodeOut])
def list_invite_codes(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(InviteCode).order_by(InviteCode.id.desc()).all()
    return [InviteCodeOut.model_validate(c) for c in rows]


@router.delete("/invite-codes/{code_id}")
def revoke_invite_code(
    code_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """作废邀请码（revoked=true）。"""
    code = db.get(InviteCode, code_id)
    if code is None:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    code.revoked = True
    db.commit()
    return {"message": "已作废"}


@router.get("/stats", response_model=StatsOut)
def stats(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(func.count(User.id)).scalar() or 0
    documents = (
        db.query(func.count(Document.id)).filter(Document.deleted_at.is_(None)).scalar() or 0
    )
    folders = db.query(func.count(Folder.id)).scalar() or 0
    annotations = db.query(func.count(Annotation.id)).scalar() or 0
    total_file_size = (
        db.query(func.coalesce(func.sum(Document.file_size), 0))
        .filter(Document.deleted_at.is_(None))
        .scalar()
        or 0
    )
    return StatsOut(
        users=users,
        documents=documents,
        folders=folders,
        annotations=annotations,
        total_file_size=total_file_size,
    )
