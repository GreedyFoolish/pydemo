"""
Product 实体的 Service 实现。

继承 BaseService[Product]，提供 Product 特有的业务方法，
重点处理多对多关联（通过 category_ids）的创建和更新。
"""

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload
from web_service.exception import DatabaseException, ErrorCode
from web_service.model.association import product_category
from web_service.model.category import Category
from web_service.model.product import Product
from web_service.service.base import BaseService
from web_service.schema.product import (
    ProductCreate,
    ProductResponse,
    ProductResponseDetail,
    ProductUpdate,
)


class ProductService(BaseService[Product]):
    """产品实体的业务服务。

    覆盖 create() 和 update() 方法以处理 category_ids 多对多关联，
    额外提供 get_detail() 方法返回包含分类和 SKU 的详细响应。
    """

    # —— 子类必须声明的类属性 ——
    _model = Product
    _create_schema = ProductCreate
    _update_schema = ProductUpdate
    _response_schema = ProductResponse

    # —— 关联处理的内部方法 ——

    async def _resolve_categories(self, category_ids: list[int]) -> list[Category]:
        """根据 ID 列表查询 Category 记录。

        若任何一个 ID 对应的分类不存在，立即抛出 NOT_FOUND。

        参数:
            category_ids: 分类 ID 列表

        返回:
            匹配的 Category ORM 实例列表（按 ID 去重）

        异常:
            DatabaseException: 当某个分类 ID 不存在，或查询数据库出错时
        """
        # 去重后查询
        unique_ids = list(set(category_ids))
        if not unique_ids:
            return []

        try:
            stmt = select(Category).where(Category.id.in_(unique_ids))
            result = await self.session.execute(stmt)
            categories = list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message="查询分类失败",
                original_error=exc,
            )

        # 检查是否所有 ID 都找到了
        found_ids = {c.id for c in categories}
        missing_ids = [cid for cid in unique_ids if cid not in found_ids]
        if missing_ids:
            # 关联不存在的分类属于"外键约束冲突"场景：
            # 语义上请求操作与当前数据状态冲突（引用的分类不存在），
            # 而不是"资源不存在"——资源不存在指的是 GET /categories/{id} 找不到分类本身。
            raise DatabaseException(
                error_code=ErrorCode.DB_FK_CONFLICT,
                message=f"部分分类不存在，无法建立关联",
                detail=f"missing_category_ids={missing_ids}",
            )

        return categories

    # —— 覆盖基类写操作，追加关联处理 ——

    async def create(self, schema: ProductCreate) -> Product:
        """创建产品并建立与分类的多对多关联。

        先创建 Product 实例（flush 拿 ID），
        再根据 category_ids 查询 Category 并赋值到 product.categories。

        参数:
            schema: ProductCreate DTO

        返回:
            新创建的 Product ORM 实例（已 flush + refresh）

        异常:
            DatabaseException: 当违反数据库约束或数据库执行出错时
        """
        try:
            # 1. 创建产品主体（排除 category_ids，它不是 Product 的直接字段）
            create_data = schema.model_dump(
                exclude={"category_ids"}, exclude_unset=True
            )
            instance = self._model(**create_data)
            self.session.add(instance)
            await self.session.flush()

            # 2. 建立分类关联（显式操作中间表，避免 ORM diff 机制在 AsyncSession 下的隐式懒加载）
            if schema.category_ids:
                categories = await self._resolve_categories(schema.category_ids)
                await self.session.execute(
                    insert(product_category),
                    [
                        {"product_id": instance.id, "category_id": c.id}
                        for c in categories
                    ],
                )
                await self.session.flush()

            # 3. refresh 拉回 server_default 字段（如 created_at）
            await self.session.refresh(instance)
            return instance
        except IntegrityError as exc:
            raise self._integrity_to_business(exc)
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_ERROR,
                message="产品创建失败",
                original_error=exc,
            )

    async def update(self, id: int, schema: ProductUpdate) -> Product:
        """更新产品信息及可选的分类关联。

        参数:
            id: 产品主键
            schema: ProductUpdate DTO

        返回:
            更新后的 Product ORM 实例（已 flush + refresh）

        异常:
            DatabaseException: 当记录不存在、违反约束或数据库执行出错时
        """
        instance = await self._require_by_id(id)

        update_data = schema.model_dump(exclude={"category_ids"}, exclude_unset=True)
        for field_name, value in update_data.items():
            setattr(instance, field_name, value)

        # 若请求中显式提供了 category_ids，则更新关联
        # None 表示不修改关联（部分更新场景）
        if schema.category_ids is not None:
            # 先校验所有分类 ID 存在（一次性批量校验）
            categories = await self._resolve_categories(schema.category_ids)
            # 显式操作中间表：先清空旧关联，再批量插入新关联
            # （避免 ORM 关系属性赋值触发 AsyncSession 下的隐式懒加载）
            await self.session.execute(
                delete(product_category).where(product_category.c.product_id == id)
            )
            if categories:
                await self.session.execute(
                    insert(product_category),
                    [{"product_id": id, "category_id": c.id} for c in categories],
                )

        try:
            await self.session.flush()
            # refresh 拉回 server_onupdate 字段（如 updated_at）
            await self.session.refresh(instance)
            return instance
        except IntegrityError as exc:
            raise self._integrity_to_business(exc)
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_ERROR,
                message=f"产品更新失败",
                original_error=exc,
            )

    # —— 详情查询 ——

    async def get_detail(self, id: int) -> ProductResponseDetail | None:
        """获取产品详情，包含关联的分类和 SKU 列表。

        使用 selectinload 预加载所有关联，
        避免后续访问触发懒加载异常。

        参数:
            id: 产品主键

        返回:
            ProductResponseDetail，不存在则返回 None

        异常:
            DatabaseException: 当数据库执行出错时
        """
        try:
            stmt = (
                select(Product)
                .options(
                    selectinload(Product.categories),
                    selectinload(Product.skus),
                )
                .where(Product.id == id)
            )
            result = await self.session.execute(stmt)
            instance = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message=f"产品详情查询失败",
                original_error=exc,
            )

        if instance is None:
            return None

        return ProductResponseDetail.model_validate(instance)
