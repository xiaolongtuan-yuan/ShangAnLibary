"""文件存储服务：落盘 / 路径解析（防穿越） / 删除 / sha256。"""

import hashlib
import uuid
from pathlib import Path

from fastapi import UploadFile


def save_upload(file: UploadFile, data_dir: str) -> tuple[str, int]:
    """保存上传文件到 <data_dir>/original/<uuid>.pdf，返回 (file_key, size)。"""
    original_dir = Path(data_dir) / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.pdf"
    file_key = f"original/{filename}"
    dest = original_dir / filename
    size = 0
    with open(dest, "wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            size += len(chunk)
    return file_key, size


def resolve_path(data_dir: str, file_key: str) -> Path:
    """把 file_key 解析为绝对路径；拒绝路径穿越。"""
    normalized = file_key.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts or ".." in parts or normalized.startswith("/"):
        raise ValueError("非法文件路径")
    return Path(data_dir).joinpath(*parts)


def delete_file(data_dir: str, file_key: str) -> None:
    """删除文件，文件不存在或路径非法时静默忽略。"""
    try:
        path = resolve_path(data_dir, file_key)
        if path.exists():
            path.unlink()
    except (ValueError, OSError):
        pass


def sha256_file(path: Path) -> str:
    """计算文件 sha256。"""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
