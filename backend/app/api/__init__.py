"""路由聚合：全部 API 模块挂载到 api_router。"""

from fastapi import APIRouter

from app.api import (
    admin,
    annotations,
    auth,
    documents,
    files,
    folders,
    my_notes,
    reader,
    search,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(folders.router)
api_router.include_router(documents.router)
api_router.include_router(documents.trash_router)
api_router.include_router(files.router)
api_router.include_router(reader.router)
api_router.include_router(annotations.router)
api_router.include_router(search.router)
api_router.include_router(my_notes.my_notes_router)
api_router.include_router(my_notes.recent_router)
api_router.include_router(admin.router)
