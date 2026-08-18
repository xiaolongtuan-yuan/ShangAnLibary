"""文档相关模型（契约 §4.3）。"""

from datetime import datetime

from pydantic import BaseModel


class OutlineItem(BaseModel):
    title: str
    page: int


class DocumentListOut(BaseModel):
    id: int
    folder_id: int | None = None
    folder_name: str | None = None
    title: str
    subject: str | None = None
    stage: str | None = None
    year: str | None = None
    source: str | None = None
    tags: list = []
    file_size: int = 0
    page_count: int | None = None
    text_extract_status: str = "pending"
    version: int = 1
    created_at: datetime
    updated_at: datetime
    my_annotation_count: int = 0
    my_progress_page: int | None = None


class DocumentDetailOut(BaseModel):
    id: int
    folder_id: int | None = None
    folder_name: str | None = None
    title: str
    subject: str | None = None
    stage: str | None = None
    year: str | None = None
    source: str | None = None
    tags: list = []
    file_size: int = 0
    page_count: int | None = None
    text_extract_status: str = "pending"
    version: int = 1
    created_at: datetime
    updated_at: datetime
    outline: list[OutlineItem] = []


class TrashDocumentOut(DocumentListOut):
    deleted_at: datetime | None = None


class UploadResult(BaseModel):
    id: int
    title: str
    file_size: int
    text_extract_status: str


class VersionOut(BaseModel):
    id: int
    version_no: int
    file_size: int = 0
    note: str | None = None
    created_at: datetime


class RollbackRequest(BaseModel):
    version_no: int
