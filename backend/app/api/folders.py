"""文件夹接口（契约 §4.2）：读全员 / 写仅管理员。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import Document, Folder, User
from app.schemas.folder import FolderCreate, FolderNode, FolderUpdate

router = APIRouter(prefix="/api/folders", tags=["folders"])


def _build_tree(folders: list[Folder]) -> list[FolderNode]:
    """按 (sort, id) 顺序把平铺文件夹组装成树。"""
    nodes: dict[int, FolderNode] = {
        f.id: FolderNode(id=f.id, name=f.name, parent_id=f.parent_id, sort=f.sort, children=[])
        for f in folders
    }
    roots: list[FolderNode] = []
    for f in folders:
        node = nodes[f.id]
        parent = nodes.get(f.parent_id) if f.parent_id else None
        if parent is not None:
            parent.children.append(node)
        else:
            roots.append(node)
    return roots


@router.get("", response_model=list[FolderNode])
def list_folders(db: Session = Depends(get_db)):
    folders = db.query(Folder).order_by(Folder.sort.asc(), Folder.id.asc()).all()
    return _build_tree(folders)


@router.post("", status_code=201, response_model=FolderNode)
def create_folder(
    body: FolderCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="文件夹名称不能为空")
    if len(name) > 64:
        raise HTTPException(status_code=400, detail="文件夹名称最长 64 个字符")
    if body.parent_id is not None:
        if db.get(Folder, body.parent_id) is None:
            raise HTTPException(status_code=400, detail="父文件夹不存在")
    dup = db.query(Folder).filter(Folder.parent_id == body.parent_id, Folder.name == name).first()
    if dup:
        raise HTTPException(status_code=400, detail="同级下已存在同名文件夹")
    folder = Folder(name=name, parent_id=body.parent_id, sort=0, created_by=admin.id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return FolderNode(id=folder.id, name=folder.name, parent_id=folder.parent_id, sort=folder.sort, children=[])


@router.patch("/{folder_id}", response_model=FolderNode)
def update_folder(
    folder_id: int,
    body: FolderUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="文件夹名称不能为空")
        if len(name) > 64:
            raise HTTPException(status_code=400, detail="文件夹名称最长 64 个字符")
        folder.name = name
    if body.sort is not None:
        folder.sort = body.sort
    if body.parent_id is not None:
        if body.parent_id == folder.id:
            raise HTTPException(status_code=400, detail="不能将文件夹移动到自身")
        # 防环：不能移动到自己的子孙节点下
        current: int | None = body.parent_id
        seen: set[int] = set()
        while current is not None and current not in seen:
            if current == folder.id:
                raise HTTPException(status_code=400, detail="不能将文件夹移动到其子文件夹下")
            seen.add(current)
            parent = db.get(Folder, current)
            current = parent.parent_id if parent else None
        folder.parent_id = body.parent_id
    dup = (
        db.query(Folder)
        .filter(
            Folder.parent_id == folder.parent_id,
            Folder.name == folder.name,
            Folder.id != folder.id,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=400, detail="同级下已存在同名文件夹")
    db.commit()
    db.refresh(folder)
    return FolderNode(id=folder.id, name=folder.name, parent_id=folder.parent_id, sort=folder.sort, children=[])


@router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    child_count = db.query(Folder).filter(Folder.parent_id == folder.id).count()
    doc_count = db.query(Document).filter(Document.folder_id == folder.id).count()
    if child_count or doc_count:
        raise HTTPException(status_code=400, detail="文件夹非空，请先清空")
    db.delete(folder)
    db.commit()
    return {"message": "已删除"}
