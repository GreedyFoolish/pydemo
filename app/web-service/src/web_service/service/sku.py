"""
Sku 实体的 Service 实现。

继承 BaseService[Sku]，提供 Sku 特有的业务方法，
重点处理外键 product_id 的存在性校验和详情查询。
"""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from web_service.exception.base import BusinessException
from web_service.exception.codes import ErrorCode
from web_service.model.product import Product
from web_service.model.sku import Sku
from web_service.service.base import BaseService
from web_service.schema.sku import (
    SkuCreate,
    SkuResponse,
    SkuResponseDetail,
    SkuUpdate,
)


class SkuService(BaseService[Sku]):
    """SKU 实体的业务服务。

    覆盖 create() 方法以校验 product_id 外键有效性，
    额外提供 get_detail() 方法返回包含所属产品的详细响应。
    """

    # —— 子类必须声明的类属性 ——
    _model = Sku
    _create_schema = SkuCreate
    _update_schema = SkuUpdate
    _response_schema = SkuResponse

    # —— 覆盖基类写操作 ——

    async def create(self, schema: SkuCreate) -> Sku:
        """创建 SKU 并校验 product_id 有效。

        参数:
            schema: SkuCreate DTO

        返回:
            新创建的 Sku ORM 实例
        """
        # 先校验所属产品存在（使用基类 _require_exists 跨模型校验）
        await self._require_exists(Product, schema.product_id, "所属产品")

        # 调用基类 create 完成实际入库
        return await super().create(schema)

    # —— 详情查询 ——

    async def get_detail(self, id: int) -> SkuResponseDetail | None:
        """获取 SKU 详情，包含所属产品信息。

        使用 selectinload 预加载 product 关联，
        避免后续访问触发懒加载异常。

        参数:
            id: SKU 主键

        返回:
            SkuResponseDetail，不存在则返回 None

        异常:
            BusinessException: 当数据库执行出错时
        """
        try:
            stmt = select(Sku).options(selectinload(Sku.product)).where(Sku.id == id)
            result = await self.session.execute(stmt)
            instance = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise BusinessException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message=f"SKU 详情查询失败（id={id}）",
                original_error=exc,
            )

        if instance is None:
            return None

        return SkuResponseDetail.model_validate(instance)
