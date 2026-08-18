"""文件夹相关模型（契约 §4.2）。"""

from __future__ import annotations

from pydantic import BaseModel


class FolderCreate(BaseModel):
    name: str
    parent_id: int | None = None


class FolderUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    sort: int | None = None


class FolderNode(BaseModel):
    id: int
    name: str
    parent_id: int | None = None
    sort: int = 0
    children: list[FolderNode] = []
