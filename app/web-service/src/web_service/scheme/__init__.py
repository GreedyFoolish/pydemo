"""DTO（数据传输对象）模块。

本模块定义了所有与 API 交互相关的 Pydantic Schema，用于：
- 请求参数校验（Create/Update DTO）
- 响应数据序列化（Response DTO）

使用字符串前向引用解决循环依赖（如 CategoryResponseDetail ↔ ProductResponse），
并在模块末尾统一调用 model_rebuild() 完成前向类型解析。
"""

from web_service.schema.base import BaseSchema
from web_service.schema.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryResponseDetail,
    CategoryUpdate,
)
from web_service.schema.product import (
    ProductCreate,
    ProductResponse,
    ProductResponseDetail,
    ProductUpdate,
)
from web_service.schema.sku import (
    SkuCreate,
    SkuResponse,
    SkuResponseDetail,
    SkuUpdate,
)

__all__ = [
    "BaseSchema",
    "CategoryCreate",
    "CategoryResponse",
    "CategoryResponseDetail",
    "CategoryUpdate",
    "ProductCreate",
    "ProductResponse",
    "ProductResponseDetail",
    "ProductUpdate",
    "SkuCreate",
    "SkuResponse",
    "SkuResponseDetail",
    "SkuUpdate",
]

# 触发所有使用了字符串前向引用的类完成类型解析
# Pydantic v2 会在这里把 "ProductResponse" 字符串替换为真实类对象
# 必须显式传入 _types_namespace，因为 ProductResponse 不在 category.py / sku.py 的运行时命名空间
CategoryResponseDetail.model_rebuild(
    _types_namespace={"ProductResponse": ProductResponse}
)
SkuResponseDetail.model_rebuild(_types_namespace={"ProductResponse": ProductResponse})
