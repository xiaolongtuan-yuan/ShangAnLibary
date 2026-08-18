"""我的笔记（契约 §4.7）与最近阅读（契约 §4.8）。"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Annotation, Document, Folder, ReadingProgress, User
from app.schemas.search import MyNoteOut, RecentDoc

my_notes_router = APIRouter(prefix="/api/my-notes", tags=["my-notes"])
recent_router = APIRouter(prefix="/api/my", tags=["my"])

TYPE_LABELS = {
    "highlight": "高亮",
    "underline": "下划线",
    "wave": "波浪线",
    "note": "笔记",
    "star": "星标",
}


def _query_my_notes(
    db: Session,
    user_id: int,
    document_id: int | None = None,
    note_type: str | None = None,
):
    query = (
        db.query(Annotation, Document, Folder.name)
        .join(Document, Document.id == Annotation.document_id)
        .outerjoin(Folder, Folder.id == Document.folder_id)
        .filter(Annotation.user_id == user_id, Document.deleted_at.is_(None))
    )
    if document_id is not None:
        query = query.filter(Annotation.document_id == document_id)
    if note_type:
        query = query.filter(Annotation.type == note_type)
    return query.order_by(Annotation.created_at.desc(), Annotation.id.desc()).all()


@my_notes_router.get("", response_model=list[MyNoteOut])
def my_notes(
    document_id: int | None = None,
    type: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """本人全部批注（跨文档），可按 document_id / type 过滤。"""
    rows = _query_my_notes(db, user.id, document_id, type)
    return [
        MyNoteOut(
            id=annotation.id,
            document_id=annotation.document_id,
            title=doc.title,
            folder_name=folder_name,
            page=annotation.page,
            type=annotation.type,
            color=annotation.color,
            content=annotation.content,
            quoted_text=annotation.quoted_text,
            created_at=annotation.created_at,
        )
        for annotation, doc, folder_name in rows
    ]


@my_notes_router.get("/export")
def export_notes(
    format: str = "md",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出笔记为 Markdown 下载。"""
    if format != "md":
        raise HTTPException(status_code=400, detail="仅支持 md 格式导出")
    rows = _query_my_notes(db, user.id)
    lines = ["# 我的笔记"]
    for annotation, doc, _folder_name in rows:
        lines.append(f"## 《{doc.title}》 第{annotation.page}页")
        if annotation.quoted_text:
            lines.append(f"> {annotation.quoted_text}")
        label = TYPE_LABELS.get(annotation.type, annotation.type)
        note_line = f"- 笔记内容（{label} {annotation.color}）"
        if annotation.content:
            note_line += f"：{annotation.content}"
        lines.append(note_line)
        lines.append("")
    content = "\n".join(lines)
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="my-notes.md"'},
    )


@recent_router.get("/recent", response_model=list[RecentDoc])
def my_recent(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """最近阅读：按阅读进度更新时间倒序取 10 条。"""
    rows = (
        db.query(ReadingProgress, Document, Folder.name)
        .join(Document, Document.id == ReadingProgress.document_id)
        .outerjoin(Folder, Folder.id == Document.folder_id)
        .filter(ReadingProgress.user_id == user.id, Document.deleted_at.is_(None))
        .order_by(ReadingProgress.updated_at.desc())
        .limit(10)
        .all()
    )
    return [
        RecentDoc(
            id=doc.id,
            title=doc.title,
            folder_name=folder_name,
            page=progress.page,
            updated_at=progress.updated_at,
        )
        for progress, doc, folder_name in rows
    ]
