"""数据库：SQLAlchemy 2.0 engine / SessionLocal / Base / get_db / init_extensions。"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""


def _create_engine(database_url: str):
    """按方言创建 engine：SQLite 需要关闭跨线程检查（TestClient 多线程用）。"""
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url, pool_pre_ping=True)


engine = _create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    """FastAPI 依赖：每个请求一个数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_extensions(engine) -> None:
    """仅 PostgreSQL 执行：pg_trgm 扩展 + 标题/页文本 GIN 索引（幂等）；SQLite 下自动跳过。"""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_documents_title_trgm "
                "ON documents USING gin (title gin_trgm_ops)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_document_pages_text_trgm "
                "ON document_pages USING gin (text gin_trgm_ops)"
            )
        )
