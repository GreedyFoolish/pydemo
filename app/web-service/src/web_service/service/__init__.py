"""Service 层包。

本包提供业务逻辑层的实现，包括：
- BaseService: 泛型基础服务类，提供统一的 CRUD 操作
- PageResult: 分页查询结果容器
- 各实体的 Service 子类：CategoryService / ProductService / SkuService

Service 类依赖 AsyncSession（由 API 层通过 FastAPI 依赖注入提供），
不自行管理数据库连接生命周期。
"""

from web_service.service.base import BaseService, PageResult
from web_service.service.category import CategoryService
from web_service.service.product import ProductService
from web_service.service.sku import SkuService
from web_service.service.upload import UploadService
from web_service.service.user import UserService

__all__ = [
    "BaseService",
    "PageResult",
    "CategoryService",
    "ProductService",
    "SkuService",
    "UploadService",
    "UserService",
]
