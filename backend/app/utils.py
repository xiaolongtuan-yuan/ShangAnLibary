"""通用小工具：统一时间处理（兼容 SQLite 与 PostgreSQL 的时区差异）。"""

from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    """统一使用 naive UTC 时间存储，避免 SQLite（naive）与 PG（aware）混用报错。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive(dt: datetime | None) -> datetime | None:
    """把任意带时区的 datetime 归一化为 naive UTC，用于跨方言比较。"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def outline_to_items(raw: Any) -> list[dict]:
    """把存储的大纲（dict 列表或 [title, page] 列表）归一化为 [{"title":..., "page":...}]。"""
    items: list[dict] = []
    for item in raw or []:
        if isinstance(item, dict):
            items.append({"title": str(item.get("title", "")), "page": int(item.get("page", 1) or 1)})
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            items.append({"title": str(item[0]), "page": int(item[1])})
    return items
