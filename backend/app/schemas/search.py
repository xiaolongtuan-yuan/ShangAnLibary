"""检索 / 我的笔记 / 最近阅读模型（契约 §4.6-4.8）。"""

from datetime import datetime

from pydantic import BaseModel


class FileHit(BaseModel):
    id: int
    title: str
    subject: str | None = None
    folder_name: str | None = None
    matched_field: str = "title"


class ContentHit(BaseModel):
    document_id: int
    title: str
    folder_name: str | None = None
    page: int
    snippet: str


class NoteHit(BaseModel):
    id: int
    document_id: int
    title: str
    folder_name: str | None = None
    page: int
    content: str | None = None
    quoted_text: str | None = None
    type: str
    color: str


class SearchResponse(BaseModel):
    files: list[FileHit] = []
    content: list[ContentHit] = []
    notes: list[NoteHit] = []


class MyNoteOut(BaseModel):
    id: int
    document_id: int
    title: str
    folder_name: str | None = None
    page: int
    type: str
    color: str
    content: str | None = None
    quoted_text: str | None = None
    created_at: datetime


class RecentDoc(BaseModel):
    id: int
    title: str
    folder_name: str | None = None
    page: int
    updated_at: datetime
