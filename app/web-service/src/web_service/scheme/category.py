"""Category 相关的 DTO 定义。

对应模型：web_service.model.category.Category
字段约束与模型中的 SQLAlchemy 列定义保持一致。
"""

from typing import TYPE_CHECKING
from pydantic import Field
from web_service.schema.base import BaseSchema

if TYPE_CHECKING:
    # 避免循环导入：ProductResponse 依赖 CategoryResponse，
    # 而 CategoryResponseDetail 又需要 ProductResponse，
    # 使用 TYPE_CHECKING + 字符串前向引用解决。
    from web_service.schema.product import ProductResponse


class CategoryCreate(BaseSchema):
    """创建分类的请求体。"""

    name: str = Field(min_length=1, max_length=50, description="分类名称")
    description: str = Field(default="", max_length=2000, description="分类描述")


class CategoryUpdate(BaseSchema):
    """更新分类的请求体，所有字段可选以支持部分更新。"""

    name: str | None = Field(
        default=None, min_length=1, max_length=50, description="分类名称"
    )
    description: str | None = Field(
        default=None, max_length=2000, description="分类描述"
    )


class CategoryResponse(BaseSchema):
    """分类的简要响应体。"""

    id: int
    name: str
    description: str = ""


class CategoryResponseDetail(BaseSchema):
    """分类的详细响应体，包含关联的产品列表。"""

    id: int
    name: str
    description: str = ""
    # 使用字符串前向引用避免循环导入
    products: list["ProductResponse"] = []
