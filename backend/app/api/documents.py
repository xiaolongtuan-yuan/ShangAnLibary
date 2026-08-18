"""文档接口（契约 §4.3）：列表/详情/上传/替换/版本/回滚/软删除 + 回收站。"""

import json
import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import (
    Annotation,
    Bookmark,
    Document,
    DocumentPage,
    DocumentVersion,
    Folder,
    ReadingProgress,
    User,
)
from app.schemas.document import (
    DocumentDetailOut,
    DocumentListOut,
    OutlineItem,
    RollbackRequest,
    TrashDocumentOut,
    UploadResult,
    VersionOut,
)
from app.services.pdf_extract import run_extract
from app.services.storage import delete_file, resolve_path, save_upload, sha256_file
from app.utils import outline_to_items, utcnow

router = APIRouter(prefix="/api/documents", tags=["documents"])
trash_router = APIRouter(prefix="/api/trash", tags=["trash"])


def _get_active_doc(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


def _folder_name_map(db: Session, folder_ids: set[int]) -> dict[int, str]:
    if not folder_ids:
        return {}
    rows = db.query(Folder.id, Folder.name).filter(Folder.id.in_(folder_ids)).all()
    return {fid: name for fid, name in rows}


def _doc_base_dict(doc: Document, folder_name: str | None) -> dict:
    return {
        "id": doc.id,
        "folder_id": doc.folder_id,
        "folder_name": folder_name,
        "title": doc.title,
        "subject": doc.subject,
        "stage": doc.stage,
        "year": doc.year,
        "source": doc.source,
        "tags": doc.tags or [],
        "file_size": doc.file_size,
        "page_count": doc.page_count,
        "text_extract_status": doc.text_extract_status,
        "version": doc.version,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
    }


def _unique_title(title: str, existing: set[str]) -> str:
    """同名自动加 ' (1)'、' (2)' 后缀。"""
    if title not in existing:
        return title
    index = 1
    while f"{title} ({index})" in existing:
        index += 1
    return f"{title} ({index})"


@router.get("", response_model=list[DocumentListOut])
def list_documents(
    folder_id: int | None = None,
    q: str | None = None,
    subject: str | None = None,
    stage: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """文档列表：folder_id=0 表示未分类（folder_id IS NULL）；按 updated_at 倒序。"""
    query = db.query(Document).filter(Document.deleted_at.is_(None))
    if folder_id == 0:
        query = query.filter(Document.folder_id.is_(None))
    elif folder_id is not None:
        query = query.filter(Document.folder_id == folder_id)
    if q:
        query = query.filter(Document.title.ilike(f"%{q}%"))
    if subject:
        query = query.filter(Document.subject == subject)
    if stage:
        query = query.filter(Document.stage == stage)
    docs = query.order_by(Document.updated_at.desc(), Document.id.desc()).all()

    folder_map = _folder_name_map(db, {d.folder_id for d in docs if d.folder_id})
    ann_counts: dict[int, int] = {}
    progress_map: dict[int, ReadingProgress] = {}
    if docs:
        doc_ids = [d.id for d in docs]
        ann_rows = (
            db.query(Annotation.document_id, func.count(Annotation.id))
            .filter(Annotation.user_id == user.id, Annotation.document_id.in_(doc_ids))
            .group_by(Annotation.document_id)
            .all()
        )
        ann_counts = {doc_id: count for doc_id, count in ann_rows}
        progress_rows = (
            db.query(ReadingProgress)
            .filter(ReadingProgress.user_id == user.id, ReadingProgress.document_id.in_(doc_ids))
            .all()
        )
        progress_map = {p.document_id: p for p in progress_rows}

    result = []
    for doc in docs:
        base = _doc_base_dict(doc, folder_map.get(doc.folder_id))
        base["my_annotation_count"] = ann_counts.get(doc.id, 0)
        progress = progress_map.get(doc.id)
        base["my_progress_page"] = progress.page if progress else None
        result.append(DocumentListOut(**base))
    return result


@router.get("/{doc_id}", response_model=DocumentDetailOut)
def document_detail(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _get_active_doc(db, doc_id)
    folder_name = None
    if doc.folder_id:
        folder = db.get(Folder, doc.folder_id)
        folder_name = folder.name if folder else None
    base = _doc_base_dict(doc, folder_name)
    return DocumentDetailOut(
        **base, outline=[OutlineItem(**item) for item in outline_to_items(doc.outline)]
    )


@router.post("", status_code=201, response_model=list[UploadResult])
def upload_documents(
    files: list[UploadFile] = File(...),
    folder_id: str | None = Form(None),
    subject: str | None = Form(None),
    stage: str | None = Form(None),
    year: str | None = Form(None),
    source: str | None = Form(None),
    tags: str | None = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """多文件上传：落盘、建 document、同名加后缀，随后后台触发文本提取。"""
    if not files:
        raise HTTPException(status_code=400, detail="请选择要上传的文件")
    # folder_id 允许为空字符串（表示未分类），故先按字符串接收再解析
    parsed_folder_id: int | None = None
    if folder_id is not None and folder_id != "":
        try:
            parsed_folder_id = int(folder_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="folder_id 无效")
    if parsed_folder_id is not None and db.get(Folder, parsed_folder_id) is None:
        raise HTTPException(status_code=400, detail="文件夹不存在")
    tag_list: list = []
    if tags:
        try:
            tag_list = json.loads(tags)
            if not isinstance(tag_list, list):
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="tags 必须是 JSON 数组字符串，如 [\"真题\"]")

    existing_titles = {
        title for (title,) in db.query(Document.title).filter(Document.deleted_at.is_(None)).all()
    }
    results: list[UploadResult] = []
    saved_keys: list[str] = []
    try:
        for f in files:
            filename = f.filename or ""
            if not filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail=f"仅支持 PDF 文件：{filename}")
            title = _unique_title(os.path.splitext(filename)[0], existing_titles)
            file_key, size = save_upload(f, settings.PDF_DATA_DIR)
            saved_keys.append(file_key)
            doc = Document(
                title=title,
                folder_id=parsed_folder_id,
                subject=subject,
                stage=stage,
                year=year,
                source=source,
                tags=tag_list,
                file_key=file_key,
                file_size=size,
                created_by=admin.id,
            )
            db.add(doc)
            db.flush()
            existing_titles.add(title)
            results.append(
                UploadResult(
                    id=doc.id, title=doc.title, file_size=doc.file_size,
                    text_extract_status=doc.text_extract_status,
                )
            )
            path = resolve_path(settings.PDF_DATA_DIR, file_key)
            background_tasks.add_task(run_extract, doc.id, str(path))
        db.commit()
    except HTTPException:
        db.rollback()
        for key in saved_keys:
            delete_file(settings.PDF_DATA_DIR, key)
        raise
    except Exception:
        db.rollback()
        for key in saved_keys:
            delete_file(settings.PDF_DATA_DIR, key)
        raise HTTPException(status_code=400, detail="文件上传失败，请稍后重试")
    return results


@router.post("/{doc_id}/replace")
def replace_document(
    doc_id: int,
    file: UploadFile = File(...),
    note: str | None = Form(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """替换文件：旧文件归档进 document_versions，版本号 +1，重新索引。"""
    doc = _get_active_doc(db, doc_id)
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    file_key, size = save_upload(file, settings.PDF_DATA_DIR)
    try:
        old_hash = None
        try:
            old_path = resolve_path(settings.PDF_DATA_DIR, doc.file_key)
            if old_path.exists():
                old_hash = sha256_file(old_path)
        except Exception:
            old_hash = None
        existing_version = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id, DocumentVersion.version_no == doc.version)
            .first()
        )
        if existing_version is not None:
            # 回滚后再替换时版本槽位可能已存在，直接覆盖归档记录
            existing_version.file_key = doc.file_key
            existing_version.file_hash = old_hash
            existing_version.note = note
            existing_version.created_by = admin.id
            existing_version.created_at = utcnow()
        else:
            db.add(
                DocumentVersion(
                    document_id=doc.id,
                    version_no=doc.version,
                    file_key=doc.file_key,
                    file_hash=old_hash,
                    note=note,
                    created_by=admin.id,
                )
            )
        doc.file_key = file_key
        doc.file_size = size
        doc.version = doc.version + 1
        doc.page_count = None
        doc.text_extract_status = "pending"
        db.commit()
    except Exception:
        db.rollback()
        delete_file(settings.PDF_DATA_DIR, file_key)
        raise HTTPException(status_code=400, detail="替换失败，请稍后重试")
    path = resolve_path(settings.PDF_DATA_DIR, file_key)
    background_tasks.add_task(run_extract, doc.id, str(path))
    return {"id": doc.id, "version": doc.version, "message": "已替换"}


@router.get("/{doc_id}/versions", response_model=list[VersionOut])
def list_versions(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _get_active_doc(db, doc_id)
    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_no.desc())
        .all()
    )
    result = []
    for v in versions:
        size = 0
        try:
            path = resolve_path(settings.PDF_DATA_DIR, v.file_key)
            size = path.stat().st_size if path.exists() else 0
        except Exception:
            size = 0
        result.append(
            VersionOut(id=v.id, version_no=v.version_no, file_size=size, note=v.note, created_at=v.created_at)
        )
    return result


@router.post("/{doc_id}/rollback")
def rollback_document(
    doc_id: int,
    body: RollbackRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """回滚到指定版本：file_key 指向版本文件，version=该版本号，重新索引。"""
    doc = _get_active_doc(db, doc_id)
    version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == doc.id, DocumentVersion.version_no == body.version_no)
        .first()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="版本不存在")
    doc.file_key = version.file_key
    doc.version = version.version_no
    doc.page_count = None
    doc.text_extract_status = "pending"
    db.commit()
    path = resolve_path(settings.PDF_DATA_DIR, doc.file_key)
    background_tasks.add_task(run_extract, doc.id, str(path))
    return {"id": doc.id, "version": doc.version, "message": "已回滚"}


@router.delete("/{doc_id}")
def delete_document(doc_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """软删除 → 回收站。"""
    doc = _get_active_doc(db, doc_id)
    doc.deleted_at = utcnow()
    db.commit()
    return {"message": "已移入回收站"}


@trash_router.get("", response_model=list[TrashDocumentOut])
def trash_list(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    docs = (
        db.query(Document)
        .filter(Document.deleted_at.isnot(None))
        .order_by(Document.deleted_at.desc())
        .all()
    )
    folder_map = _folder_name_map(db, {d.folder_id for d in docs if d.folder_id})
    result = []
    for doc in docs:
        base = _doc_base_dict(doc, folder_map.get(doc.folder_id))
        base["deleted_at"] = doc.deleted_at
        base["my_annotation_count"] = 0
        base["my_progress_page"] = None
        result.append(TrashDocumentOut(**base))
    return result


@trash_router.post("/{doc_id}/restore")
def restore_document(doc_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if doc is None or doc.deleted_at is None:
        raise HTTPException(status_code=404, detail="文档不在回收站中")
    doc.deleted_at = None
    db.commit()
    return {"message": "已恢复"}


@trash_router.delete("/{doc_id}")
def purge_document(doc_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """彻底删除：级联删除文件、版本、页文本、批注、书签、进度。"""
    doc = db.get(Document, doc_id)
    if doc is None or doc.deleted_at is None:
        raise HTTPException(status_code=404, detail="文档不在回收站中")
    db.query(Annotation).filter(Annotation.document_id == doc.id).delete(synchronize_session=False)
    db.query(Bookmark).filter(Bookmark.document_id == doc.id).delete(synchronize_session=False)
    db.query(ReadingProgress).filter(ReadingProgress.document_id == doc.id).delete(
        synchronize_session=False
    )
    db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).delete(synchronize_session=False)
    versions = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).all()
    for v in versions:
        delete_file(settings.PDF_DATA_DIR, v.file_key)
    db.query(DocumentVersion).filter(DocumentVersion.document_id == doc.id).delete(
        synchronize_session=False
    )
    delete_file(settings.PDF_DATA_DIR, doc.file_key)
    db.delete(doc)
    db.commit()
    return {"message": "已彻底删除"}
