"""阅读会话接口（契约 §4.5）：会话聚合 + 进度 upsert。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Annotation, Bookmark, Document, Folder, ReadingProgress, User
from app.schemas.annotation import (
    AnnotationOut,
    BookmarkOut,
    ProgressOut,
    ProgressUpsert,
    ReaderSession,
)
from app.schemas.document import DocumentDetailOut, OutlineItem
from app.services.security import make_file_url
from app.utils import outline_to_items

router = APIRouter(prefix="/api/reader", tags=["reader"])


def _get_active_doc(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.get("/{doc_id}", response_model=ReaderSession)
def reader_session(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """阅读会话：文档详情 + 签名文件 URL + 本人批注/书签/进度。"""
    doc = _get_active_doc(db, doc_id)
    folder_name = None
    if doc.folder_id:
        folder = db.get(Folder, doc.folder_id)
        folder_name = folder.name if folder else None
    detail = DocumentDetailOut(
        id=doc.id,
        folder_id=doc.folder_id,
        folder_name=folder_name,
        title=doc.title,
        subject=doc.subject,
        stage=doc.stage,
        year=doc.year,
        source=doc.source,
        tags=doc.tags or [],
        file_size=doc.file_size,
        page_count=doc.page_count,
        text_extract_status=doc.text_extract_status,
        version=doc.version,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        outline=[OutlineItem(**item) for item in outline_to_items(doc.outline)],
    )
    annotations = (
        db.query(Annotation)
        .filter(Annotation.user_id == user.id, Annotation.document_id == doc.id)
        .order_by(Annotation.page.asc(), Annotation.id.asc())
        .all()
    )
    bookmarks = (
        db.query(Bookmark)
        .filter(Bookmark.user_id == user.id, Bookmark.document_id == doc.id)
        .order_by(Bookmark.page.asc())
        .all()
    )
    progress = (
        db.query(ReadingProgress)
        .filter(ReadingProgress.user_id == user.id, ReadingProgress.document_id == doc.id)
        .first()
    )
    return ReaderSession(
        document=detail,
        file_url=make_file_url(doc.id),
        annotations=[AnnotationOut.model_validate(a) for a in annotations],
        bookmarks=[BookmarkOut.model_validate(b) for b in bookmarks],
        progress=ProgressOut.model_validate(progress) if progress else None,
    )


@router.put("/{doc_id}/progress", response_model=ProgressOut)
def save_progress(
    doc_id: int,
    body: ProgressUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存阅读进度（upsert，按 user+doc 唯一）。"""
    _get_active_doc(db, doc_id)
    progress = (
        db.query(ReadingProgress)
        .filter(ReadingProgress.user_id == user.id, ReadingProgress.document_id == doc_id)
        .first()
    )
    if progress is None:
        progress = ReadingProgress(user_id=user.id, document_id=doc_id, page=body.page, scroll_y=body.scroll_y)
        db.add(progress)
    else:
        progress.page = body.page
        progress.scroll_y = body.scroll_y
    db.commit()
    db.refresh(progress)
    return ProgressOut(page=progress.page, scroll_y=progress.scroll_y)
