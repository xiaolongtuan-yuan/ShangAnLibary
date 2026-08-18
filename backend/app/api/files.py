"""文件流接口（契约 §4.4）：签名 URL 签发 + 流式输出（X-Accel-Redirect / FileResponse）。"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Document, User
from app.services.security import make_file_url, verify_file_signature
from app.services.storage import resolve_path

router = APIRouter(prefix="/api/files", tags=["files"])


def _get_active_doc(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.get("/{doc_id}/url")
def file_url(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """签发 5 分钟有效的相对签名 URL。"""
    doc = _get_active_doc(db, doc_id)
    return {"url": make_file_url(doc.id)}


@router.get("/stream/{doc_id}")
def stream_file(doc_id: int, exp: str = "", sig: str = "", db: Session = Depends(get_db)):
    """校验签名与过期（失败 403）；USE_X_ACCEL=true 返回 X-Accel-Redirect 头（空 body），
    false 时用 FileResponse 直接输出（支持 Range 分段加载）。"""
    doc = _get_active_doc(db, doc_id)
    try:
        exp_value = int(exp)
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="签名无效或已过期")
    if not verify_file_signature(doc.id, exp_value, sig):
        raise HTTPException(status_code=403, detail="签名无效或已过期")

    if settings.USE_X_ACCEL:
        quoted_title = quote(doc.title, safe="")
        return Response(
            status_code=200,
            headers={
                "X-Accel-Redirect": f"/protected/{doc.file_key}",
                "Content-Type": "application/pdf",
                "Content-Disposition": f"inline; filename*=UTF-8''{quoted_title}",
            },
        )
    path = resolve_path(settings.PDF_DATA_DIR, doc.file_key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path=path, filename=doc.title, media_type="application/pdf")
