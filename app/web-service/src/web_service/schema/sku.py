"""Sku 相关的 DTO 定义。

对应模型：web_service.model.sku.Sku
字段约束与模型中的 SQLAlchemy 列定义保持一致。
"""

from decimal import Decimal
from typing import TYPE_CHECKING, Any
from pydantic import Field
from web_service.schema.base import BaseSchema

if TYPE_CHECKING:
    from web_service.schema.product import ProductResponse


class SkuCreate(BaseSchema):
    """创建 SKU 的请求体。"""

    product_id: int = Field(gt=0, description="所属产品 ID")
    sku_code: str = Field(min_length=1, max_length=50, description="SKU 编码")
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2, description="价格")
    stock: int = Field(default=0, ge=0, description="库存")
    attrs: dict[str, Any] = Field(description="规格属性（JSON）")
    image_url: str = Field(min_length=1, max_length=500, description="图片地址")


class SkuUpdate(BaseSchema):
    """更新 SKU 的请求体，所有字段可选以支持部分更新。"""

    sku_code: str | None = Field(
        default=None, min_length=1, max_length=50, description="SKU 编码"
    )
    price: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2, description="价格"
    )
    stock: int | None = Field(default=None, ge=0, description="库存")
    attrs: dict[str, Any] | None = Field(default=None, description="规格属性（JSON）")
    image_url: str | None = Field(
        default=None, min_length=1, max_length=500, description="图片地址"
    )


class SkuResponse(BaseSchema):
    """SKU 的简要响应体。"""

    id: int
    product_id: int
    sku_code: str
    price: Decimal
    stock: int = 0
    attrs: dict[str, Any]
    image_url: str


class SkuResponseDetail(BaseSchema):
    """SKU 的详细响应体，包含关联的产品信息。"""

    id: int
    product_id: int
    sku_code: str
    price: Decimal
    stock: int = 0
    attrs: dict[str, Any]
    image_url: str
    # 使用字符串前向引用避免循环导入
    product: "ProductResponse" | None = None
