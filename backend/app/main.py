"""FastAPI 应用入口：lifespan 建表 + 扩展初始化，CORS，路由注册，健康检查。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  确保所有模型注册到 Base.metadata
from app.api import api_router
from app.config import settings
from app.database import Base, engine, init_extensions


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    init_extensions(engine)
    yield


app = FastAPI(title="上岸书房 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
