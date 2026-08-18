"""PDF 文本提取流水线（契约 §5）：页数 / 逐页文本 / 扁平大纲，失败自动重试。"""

import logging
import time
from typing import Any

from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Document, DocumentPage

logger = logging.getLogger(__name__)

MAX_RETRIES = 3  # 初次尝试失败后最多再重试 3 次


def _flatten_outline(items: list[Any] | None) -> list[tuple[str, int]]:
    """把 pypdf get_outlines() 的结果扁平化为 [(title, page)]，忽略层级。

    item 可能是嵌套 list（有子级）、Destination 对象或 (title, destination) 元组。
    页码取 destination.page_number + 1。
    """
    result: list[tuple[str, int]] = []
    for item in items or []:
        if isinstance(item, list):
            result.extend(_flatten_outline(item))
            continue
        if isinstance(item, (tuple, list)) and len(item) >= 1:
            title = str(item[0])
            dest = item[1] if len(item) >= 2 else None
        else:
            title = str(getattr(item, "title", item))
            dest = getattr(item, "page", None)
        page_number = None
        if dest is not None:
            try:
                page_number = getattr(dest, "page_number", None)
                if page_number is None and hasattr(dest, "get_object"):
                    page_number = getattr(dest.get_object(), "page_number", None)
            except Exception:
                page_number = None
        if page_number is not None:
            result.append((title, page_number + 1))
    return result


def _write_pages(db: Session, document_id: int, pages: list[tuple[int, str]]) -> None:
    """先删旧页文本，再批量插入新页。"""
    db.query(DocumentPage).filter(DocumentPage.document_id == document_id).delete(
        synchronize_session=False
    )
    for page_no, text in pages:
        db.add(DocumentPage(document_id=document_id, page_no=page_no, text=text))


def extract(document_id: int, file_path: str, db: Session) -> None:
    """提取页数/逐页文本/大纲并入库；开始时置 processing，成功置 done，最终失败置 failed。"""
    doc = db.get(Document, document_id)
    if doc is None:
        return
    doc.text_extract_status = "processing"
    db.commit()

    last_error: Exception | None = None
    # 初次尝试 + 最多 3 次重试，共 4 次
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            reader = PdfReader(file_path)
            page_count = len(reader.pages)
            pages: list[tuple[int, str]] = []
            for index, page in enumerate(reader.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                pages.append((index, text))
            outline = _flatten_outline(reader.get_outlines())

            _write_pages(db, document_id, pages)
            doc = db.get(Document, document_id)
            if doc is None:
                return
            doc.page_count = page_count
            # JSON 列只支持 dict/list，元组需转成 dict 存储，读回后可直接用
            doc.outline = [{"title": title, "page": page} for title, page in outline]
            doc.text_extract_status = "done"
            db.commit()
            logger.info("文档 %s 文本提取完成：%s 页", document_id, page_count)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning("文档 %s 文本提取第 %s 次失败：%s", document_id, attempt, exc)
            if attempt <= MAX_RETRIES:
                time.sleep(1)

    doc = db.get(Document, document_id)
    if doc is not None:
        doc.text_extract_status = "failed"
        db.commit()
    logger.error("文档 %s 文本提取最终失败：%s", document_id, last_error)


def run_extract(document_id: int, file_path: str) -> None:
    """后台任务入口：使用独立数据库会话执行提取，不依赖请求会话。"""
    db = SessionLocal()
    try:
        extract(document_id, file_path, db)
    except Exception:
        db.rollback()
        try:
            doc = db.get(Document, document_id)
            if doc is not None:
                doc.text_extract_status = "failed"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()
