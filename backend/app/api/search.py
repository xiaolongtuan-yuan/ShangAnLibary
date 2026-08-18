"""全局检索接口（契约 §4.6）：q 必填非空，scope 过滤三组结果。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.search import SearchResponse
from app.services import search as search_service

router = APIRouter(prefix="/api", tags=["search"])

VALID_SCOPES = {"all", "file", "content", "note"}


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = "",
    scope: str = "all",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    keyword = q.strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="请输入搜索关键词")
    if scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail="scope 参数无效")

    result = SearchResponse()
    if scope in ("all", "file"):
        result.files = search_service.search_files(db, keyword)
    if scope in ("all", "content"):
        result.content = search_service.search_content(db, keyword)
    if scope in ("all", "note"):
        result.notes = search_service.search_notes(db, keyword, user.id)
    return result
