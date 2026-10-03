"""Product 相关的 DTO 定义。

对应模型：web_service.model.product.Product
字段约束与模型中的 SQLAlchemy 列定义保持一致。
"""

from datetime import datetime
from pydantic import Field
from web_service.schema.base import BaseSchema
from web_service.schema.category import CategoryResponse
from web_service.schema.sku import SkuResponse


class ProductCreate(BaseSchema):
    """创建产品的请求体。"""

    name: str = Field(min_length=1, max_length=200, description="产品名称")
    description: str = Field(default="", max_length=2000, description="产品描述")
    brand: str | None = Field(
        default=None, min_length=1, max_length=100, description="品牌"
    )
    # 通过 ID 列表关联分类，避免循环嵌套
    category_ids: list[int] = Field(
        default_factory=list, description="关联分类 ID 列表"
    )


class ProductUpdate(BaseSchema):
    """更新产品的请求体，所有字段可选以支持部分更新。"""

    name: str | None = Field(
        default=None, min_length=1, max_length=200, description="产品名称"
    )
    description: str | None = Field(
        default=None, max_length=2000, description="产品描述"
    )
    brand: str | None = Field(
        default=None, min_length=1, max_length=100, description="品牌"
    )
    category_ids: list[int] | None = Field(default=None, description="关联分类 ID 列表")


class ProductResponse(BaseSchema):
    """产品的简要响应体（不包含嵌套的分类和 SKU 详情）。"""

    id: int
    name: str
    description: str = ""
    brand: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductResponseDetail(BaseSchema):
    """产品的详细响应体，包含关联的分类和 SKU。"""

    id: int
    name: str
    description: str = ""
    brand: str | None = None
    created_at: datetime
    updated_at: datetime
    # 嵌套关联对象
    categories: list[CategoryResponse] = []
    skus: list[SkuResponse] = []
