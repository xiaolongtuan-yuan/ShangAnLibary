"""批注与书签接口（契约 §4.5）：全部为本人数据，越权一律 404。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Annotation, Bookmark, Document, User
from app.schemas.annotation import (
    AnnotationCreate,
    AnnotationOut,
    AnnotationUpdate,
    BookmarkCreate,
    BookmarkOut,
)

router = APIRouter(prefix="/api", tags=["annotations"])

VALID_TYPES = {"highlight", "underline", "wave", "note", "star"}


def _get_active_doc(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.get("/documents/{doc_id}/annotations", response_model=list[AnnotationOut])
def list_annotations(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """本人批注列表。"""
    _get_active_doc(db, doc_id)
    rows = (
        db.query(Annotation)
        .filter(Annotation.user_id == user.id, Annotation.document_id == doc_id)
        .order_by(Annotation.page.asc(), Annotation.id.asc())
        .all()
    )
    return [AnnotationOut.model_validate(a) for a in rows]


@router.post("/documents/{doc_id}/annotations", status_code=201, response_model=AnnotationOut)
def create_annotation(
    doc_id: int,
    body: AnnotationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_active_doc(db, doc_id)
    if body.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="批注类型无效")
    if body.page < 1:
        raise HTTPException(status_code=400, detail="页码无效")
    annotation = Annotation(
        user_id=user.id,
        document_id=doc_id,
        page=body.page,
        type=body.type,
        color=body.color,
        rect=body.rect,
        content=body.content,
        quoted_text=body.quoted_text,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return AnnotationOut.model_validate(annotation)


@router.patch("/annotations/{annotation_id}", response_model=AnnotationOut)
def update_annotation(
    annotation_id: int,
    body: AnnotationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改本人批注（均可选）；非本人数据返回 404。"""
    annotation = (
        db.query(Annotation)
        .filter(Annotation.id == annotation_id, Annotation.user_id == user.id)
        .first()
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="批注不存在")
    data = body.model_dump(exclude_unset=True)
    if "type" in data and data["type"] not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="批注类型无效")
    if "page" in data and data["page"] < 1:
        raise HTTPException(status_code=400, detail="页码无效")
    for field, value in data.items():
        setattr(annotation, field, value)
    db.commit()
    db.refresh(annotation)
    return AnnotationOut.model_validate(annotation)


@router.delete("/annotations/{annotation_id}")
def delete_annotation(
    annotation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    annotation = (
        db.query(Annotation)
        .filter(Annotation.id == annotation_id, Annotation.user_id == user.id)
        .first()
    )
    if annotation is None:
        raise HTTPException(status_code=404, detail="批注不存在")
    db.delete(annotation)
    db.commit()
    return {"message": "已删除"}


@router.get("/documents/{doc_id}/bookmarks", response_model=list[BookmarkOut])
def list_bookmarks(
    doc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """本人书签列表。"""
    _get_active_doc(db, doc_id)
    rows = (
        db.query(Bookmark)
        .filter(Bookmark.user_id == user.id, Bookmark.document_id == doc_id)
        .order_by(Bookmark.page.asc())
        .all()
    )
    return [BookmarkOut.model_validate(b) for b in rows]


@router.post("/documents/{doc_id}/bookmarks", status_code=201, response_model=BookmarkOut)
def create_bookmark(
    doc_id: int,
    body: BookmarkCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_active_doc(db, doc_id)
    if body.page < 1:
        raise HTTPException(status_code=400, detail="页码无效")
    dup = (
        db.query(Bookmark)
        .filter(
            Bookmark.user_id == user.id,
            Bookmark.document_id == doc_id,
            Bookmark.page == body.page,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=400, detail="该页已有书签")
    bookmark = Bookmark(user_id=user.id, document_id=doc_id, page=body.page, label=body.label)
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return BookmarkOut.model_validate(bookmark)


@router.delete("/bookmarks/{bookmark_id}")
def delete_bookmark(
    bookmark_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bookmark = (
        db.query(Bookmark)
        .filter(Bookmark.id == bookmark_id, Bookmark.user_id == user.id)
        .first()
    )
    if bookmark is None:
        raise HTTPException(status_code=404, detail="书签不存在")
    db.delete(bookmark)
    db.commit()
    return {"message": "已删除"}
