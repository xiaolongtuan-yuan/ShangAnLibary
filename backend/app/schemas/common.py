"""通用 Pydantic 模型。"""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """支持从 SQLAlchemy ORM 对象直接构造（from_attributes）。"""

    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str
