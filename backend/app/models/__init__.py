"""模型注册：导入本包即把所有表注册到 Base.metadata。"""

from app.models.annotation import Annotation
from app.models.bookmark import Bookmark
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.document_version import DocumentVersion
from app.models.folder import Folder
from app.models.invite_code import InviteCode
from app.models.reading_progress import ReadingProgress
from app.models.user import User

__all__ = [
    "Annotation",
    "Bookmark",
    "Document",
    "DocumentPage",
    "DocumentVersion",
    "Folder",
    "InviteCode",
    "ReadingProgress",
    "User",
]
