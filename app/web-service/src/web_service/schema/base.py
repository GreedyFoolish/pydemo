"""Schema 基础类定义。

本模块提供 DTO 类的公共基类，配置 Pydantic v2 的通用行为。
"""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """所有 DTO 的统一基类。

    配置 from_attributes=True 使得 Schema 可以直接从 SQLAlchemy ORM 模型实例构造：
        schema = CategoryRead.model_validate(orm_instance)
    """

    model_config = ConfigDict(
        from_attributes=True,
        # 忽略额外字段，防止 ORM 加载的懒加载关系导致验证失败
        extra="ignore",
    )
