"""检索服务（契约 §4.6）：files / content / notes 三组，全部用 ilike。"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Annotation, Document, DocumentPage, Folder
from app.schemas.search import ContentHit, FileHit, NoteHit

SNIPPET_RADIUS = 30


def _make_snippet(text: str, keyword: str) -> str:
    """取首个命中位置前后各 30 字符生成片段。"""
    index = text.lower().find(keyword.lower())
    if index < 0:
        index = text.find(keyword)
    if index < 0:
        return text[: SNIPPET_RADIUS * 2].replace("\n", " ")
    start = max(0, index - SNIPPET_RADIUS)
    end = min(len(text), index + len(keyword) + SNIPPET_RADIUS)
    snippet = text[start:end].replace("\n", " ")
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def search_files(db: Session, keyword: str) -> list[FileHit]:
    """文件名命中：documents.title ilike。"""
    rows = (
        db.query(Document, Folder.name)
        .outerjoin(Folder, Folder.id == Document.folder_id)
        .filter(Document.deleted_at.is_(None), Document.title.ilike(f"%{keyword}%"))
        .order_by(Document.updated_at.desc())
        .all()
    )
    return [
        FileHit(id=doc.id, title=doc.title, subject=doc.subject, folder_name=folder_name)
        for doc, folder_name in rows
    ]


def search_content(db: Session, keyword: str) -> list[ContentHit]:
    """页文本命中：document_pages.text ilike，排除已删除文档，LIMIT 50。"""
    rows = (
        db.query(DocumentPage, Document, Folder.name)
        .join(Document, Document.id == DocumentPage.document_id)
        .outerjoin(Folder, Folder.id == Document.folder_id)
        .filter(Document.deleted_at.is_(None), DocumentPage.text.ilike(f"%{keyword}%"))
        .order_by(func.length(DocumentPage.text).asc())
        .limit(50)
        .all()
    )
    return [
        ContentHit(
            document_id=page.document_id,
            title=doc.title,
            folder_name=folder_name,
            page=page.page_no,
            snippet=_make_snippet(page.text, keyword),
        )
        for page, doc, folder_name in rows
    ]


def search_notes(db: Session, keyword: str, user_id: int) -> list[NoteHit]:
    """本人批注命中：annotations.content / quoted_text ilike（强制 user_id 隔离）。"""
    rows = (
        db.query(Annotation, Document, Folder.name)
        .join(Document, Document.id == Annotation.document_id)
        .outerjoin(Folder, Folder.id == Document.folder_id)
        .filter(
            Annotation.user_id == user_id,
            Document.deleted_at.is_(None),
            (Annotation.content.ilike(f"%{keyword}%"))
            | (Annotation.quoted_text.ilike(f"%{keyword}%")),
        )
        .order_by(Annotation.updated_at.desc())
        .all()
    )
    return [
        NoteHit(
            id=annotation.id,
            document_id=annotation.document_id,
            title=doc.title,
            folder_name=folder_name,
            page=annotation.page,
            content=annotation.content,
            quoted_text=annotation.quoted_text,
            type=annotation.type,
            color=annotation.color,
        )
        for annotation, doc, folder_name in rows
    ]
