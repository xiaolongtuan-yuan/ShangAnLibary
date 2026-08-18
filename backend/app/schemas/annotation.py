"""批注/书签/进度/阅读会话模型（契约 §4.5）。"""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel
from app.schemas.document import DocumentDetailOut


class AnnotationCreate(BaseModel):
    type: str
    page: int
    color: str = "#ffe14d"
    rect: dict | None = None
    content: str | None = None
    quoted_text: str | None = None


class AnnotationUpdate(BaseModel):
    type: str | None = None
    page: int | None = None
    color: str | None = None
    rect: dict | None = None
    content: str | None = None
    quoted_text: str | None = None


class AnnotationOut(ORMModel):
    id: int
    document_id: int
    page: int
    type: str
    color: str
    rect: dict | None = None
    content: str | None = None
    quoted_text: str | None = None
    created_at: datetime
    updated_at: datetime


class BookmarkCreate(BaseModel):
    page: int
    label: str | None = None


class BookmarkOut(ORMModel):
    id: int
    page: int
    label: str | None = None
    created_at: datetime


class ProgressUpsert(BaseModel):
    page: int
    scroll_y: float = 0.0


class ProgressOut(ORMModel):
    page: int
    scroll_y: float


class ReaderSession(BaseModel):
    document: DocumentDetailOut
    file_url: str
    annotations: list[AnnotationOut] = []
    bookmarks: list[BookmarkOut] = []
    progress: ProgressOut | None = None
