"""命令行工具（契约 §6）：python -m app.cli create-admin | ensure-admin。"""

import getpass
import sys

import app.models  # noqa: F401  确保模型注册
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import User
from app.services.security import hash_password


def _init_tables() -> None:
    Base.metadata.create_all(bind=engine)


def _ensure_admin(username: str, password: str, email: str) -> bool:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing is not None:
            print(f"管理员 {username} 已存在，跳过创建")
            return False
        db.add(
            User(username=username, email=email, password_hash=hash_password(password), role="admin")
        )
        db.commit()
        print(f"管理员 {username} 创建成功")
        return True
    finally:
        db.close()


def create_admin() -> None:
    """交互式或读 INIT_ADMIN_* 环境变量创建管理员（已存在则提示）。"""
    _init_tables()
    username = settings.INIT_ADMIN_USERNAME
    email = settings.INIT_ADMIN_EMAIL
    password = settings.INIT_ADMIN_PASSWORD
    if not password:
        password = getpass.getpass("请输入管理员密码（至少 8 位）：")
    if not password or len(password) < 8:
        print("密码至少 8 位，创建失败")
        sys.exit(1)
    _ensure_admin(username, password, email)


def ensure_admin() -> None:
    """幂等创建管理员（容器启动用，读环境变量；密码缺失时提示并跳过）。"""
    _init_tables()
    password = settings.INIT_ADMIN_PASSWORD
    if not password:
        print("未设置 INIT_ADMIN_PASSWORD，跳过管理员初始化")
        return
    _ensure_admin(settings.INIT_ADMIN_USERNAME, password, settings.INIT_ADMIN_EMAIL)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "create-admin":
        create_admin()
    elif command == "ensure-admin":
        ensure_admin()
    else:
        print("用法：python -m app.cli create-admin | ensure-admin")
        sys.exit(1)
