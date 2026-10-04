"""
Service 层基础类定义。

本模块提供：
- PageResult: 泛型分页结果 dataclass
- BaseService: 泛型基础服务类，为所有实体 Service 子类提供统一的：
  - 依赖注入：接收 AsyncSession，由 API 层控制生命周期
  - 通用 CRUD：get_by_id / list / list_paged / count / create / update / delete
  - 异常转换：将 SQLAlchemy 原始异常统一包装为 DatabaseException

子类只需声明 ORM 模型类型和对应的 Schema 类，即可获得完整的类型安全 CRUD。
"""

from dataclasses import dataclass
from typing import Any, Generic, Type, TypeVar
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from web_service.exception import DatabaseException, ErrorCode

# 绑定到 DeclarativeBase（即 model/base.py 中的 Base），确保泛型类型安全
ModelType = TypeVar("ModelType", bound=DeclarativeBase)
# PageResult 使用的独立类型变量，避免与 ModelType 冲突
T = TypeVar("T")


@dataclass
class PageResult(Generic[T]):
    """分页查询结果。

    泛型参数 T 指定 items 中元素的类型（通常是 Response DTO）。
    """

    items: list[T]
    total: int
    page: int
    page_size: int

    # 便捷属性：总页数
    @property
    def total_pages(self) -> int:
        """根据 total 和 page_size 计算总页数。"""
        if self.page_size <= 0:
            return 0
        return max(0, (self.total + self.page_size - 1) // self.page_size)


class BaseService(Generic[ModelType]):
    """所有 Service 的泛型基类。

    通过 Generic[ModelType] 为子类提供类型安全的 CRUD 操作。
    子类必须覆盖以下类属性以绑定具体实现：

        class CategoryService(BaseService[Category]):
            _model = Category                    # ORM 模型类
            _create_schema = CategoryCreate      # 创建请求 DTO
            _update_schema = CategoryUpdate      # 更新请求 DTO
            _response_schema = CategoryResponse # 简要响应 DTO

    构造函数说明：
        session: 由 API 层通过 FastAPI 依赖注入提供的 AsyncSession，
                 本 Service 不自行创建或关闭 session，
                 事务提交/回滚也由 API 层统一管理。
    """

    # —— 以下类属性必须由子类覆盖声明 ——
    # ORM 模型类（继承自 model/base.Base）
    _model: Type[ModelType]
    # 创建请求 DTO 类（继承自 schema/base.BaseSchema）
    _create_schema: Type[Any]
    # 更新请求 DTO 类（继承自 schema/base.BaseSchema）
    _update_schema: Type[Any]
    # 简要响应 DTO 类（继承自 schema/base.BaseSchema）
    _response_schema: Type[Any]

    def __init__(self, session: AsyncSession) -> None:
        """构造基础 Service。

        参数:
            session: 数据库异步会话，由 API 层依赖注入提供
        """
        self.session = session

    # —— 通用查询 ——

    async def get_by_id(self, id: int) -> ModelType | None:
        """按 ID 查询单条记录（返回 ORM 实例或 None）。

        若记录不存在，返回 None 而非抛异常，调用方自行决定后续处理。
        若需要"不存在就中断流程"的场景（如 update / delete 内部），
        请使用 _require_by_id()，它会在不存在时抛出 DatabaseException。

        参数:
            id: 记录主键

        返回:
            匹配的 ORM 模型实例，不存在则返回 None

        异常:
            DatabaseException: 当数据库执行出错时（code=DB_OPERATIONAL_ERROR）
        """
        try:
            stmt = select(self._model).where(self._model.id == id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message=f"{self._model.__name__} 查询失败",
                original_error=exc,
            )

    async def _require_by_id(self, id: int) -> ModelType:
        """按 ID 查询记录，不存在时抛出 DatabaseException(NOT_FOUND)。

        用于"必须存在才能继续"的内部流程，如 update / delete。
        外部查询场景请使用 get_by_id() 并自行处理 None。

        参数:
            id: 记录主键

        返回:
            匹配的 ORM 模型实例

        异常:
            DatabaseException: 当记录不存在时（code=NOT_FOUND）
        """
        instance = await self.get_by_id(id)
        if instance is None:
            raise DatabaseException(
                error_code=ErrorCode.NOT_FOUND,
                message=f"{self._model.__name__} 不存在",
                detail=f"model={self._model.__name__}, id={id}",
            )
        return instance

    async def _require_exists(
        self, model_cls: Type[Any], id: int, label: str | None = None
    ) -> None:
        """校验任意模型的某条记录是否存在，不存在则抛 DatabaseException(NOT_FOUND)。

        用于跨模型外键校验场景，例如 SkuService.create 需要检查 product_id
        对应的 Product 是否存在，但 SkuService 不继承 BaseService[Product]。

        参数:
            model_cls: 被检查的 ORM 模型类（可以是任意继承自 model.base.Base 的类）
            id: 要检查的主键值
            label: 错误消息中使用的友好名称，不传则用 model_cls.__name__

        异常:
            DatabaseException: 当对应记录不存在（code=NOT_FOUND）或查询数据库出错时
        """
        try:
            stmt = select(model_cls).where(model_cls.id == id)
            result = await self.session.execute(stmt)
            exists = result.scalar_one_or_none() is not None
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message=f"{model_cls.__name__} 存在性校验失败",
                original_error=exc,
            )

        if not exists:
            display = label or model_cls.__name__
            raise DatabaseException(
                error_code=ErrorCode.NOT_FOUND,
                message=f"{display}不存在",
                detail=f"model={model_cls.__name__}, id={id}",
            )

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[ModelType]:
        """分页查询记录列表（返回 ORM 实例列表）。

        参数:
            skip: 跳过前 N 条记录，用于分页
            limit: 最多返回 N 条记录
            **filters: 额外的等值过滤条件，如 name="xxx"
                       键名必须与模型列名一致，例如 CategoryService.list(name="电子")

        返回:
            ORM 模型实例列表

        异常:
            DatabaseException: 当数据库执行出错时（code=DB_OPERATIONAL_ERROR）
        """
        try:
            stmt = select(self._model)

            # 动态添加等值过滤
            for key, value in filters.items():
                if value is not None:
                    stmt = stmt.where(getattr(self._model, key) == value)

            stmt = stmt.offset(skip).limit(limit)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message=f"{self._model.__name__} 列表查询失败",
                original_error=exc,
            )

    async def count(self, **filters: Any) -> int:
        """查询符合条件的记录总数。

        参数:
            **filters: 等值过滤条件，与 list() 的 filters 参数用法一致

        返回:
            记录总数

        异常:
            DatabaseException: 当数据库执行出错时（code=DB_OPERATIONAL_ERROR）
        """
        try:
            stmt = select(func.count()).select_from(self._model)
            for key, value in filters.items():
                if value is not None:
                    stmt = stmt.where(getattr(self._model, key) == value)

            result = await self.session.execute(stmt)
            return result.scalar_one() or 0
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message=f"{self._model.__name__} 计数查询失败",
                original_error=exc,
            )

    async def list_paged(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "id",
        ascending: bool = True,
        **filters: Any,
    ) -> PageResult[Any]:
        """分页查询记录，返回 PageResult[ResponseSchema]（已转为 DTO）。

        与 list() 的区别：
        - 返回 PageResult 包含 total / page / page_size 元数据
        - 直接返回 Response DTO 而非 ORM 实例，可直接用于 API 响应
        - 支持排序

        参数:
            page: 页码（从 1 开始）
            page_size: 每页条数
            order_by: 排序字段名（模型列名，如 "id" 或 "created_at"）
            ascending: True 升序，False 降序
            **filters: 等值过滤条件，与 list() 用法一致

        返回:
            PageResult，items 已转换为 _response_schema 类型
        """
        # 1. 先查总数（复用 count 逻辑）
        total = await self.count(**filters)

        # 2. 查当前页数据
        offset = (page - 1) * page_size

        stmt = select(self._model)
        for key, value in filters.items():
            if value is not None:
                stmt = stmt.where(getattr(self._model, key) == value)

        # 动态排序
        order_col = getattr(self._model, order_by)
        stmt = stmt.order_by(order_col.asc() if ascending else order_col.desc())

        stmt = stmt.offset(offset).limit(page_size)
        result = await self.session.execute(stmt)
        instances = list(result.scalars().all())

        # 3. 转为 Response DTO
        items = self.to_response_list(instances)

        return PageResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    # —— 通用写操作 ——

    async def create(self, schema: Any) -> ModelType:
        """创建新记录。

        参数:
            schema: 创建请求 DTO 实例（_create_schema）

        返回:
            新创建的 ORM 模型实例（已 flush + refresh，自增主键和 server_default 字段已就绪）

        异常:
            DatabaseException: 当违反数据库约束或数据库执行出错时
        """
        try:
            # 从 DTO 构造 ORM 实例，exclude_unset 排除未设置的字段
            # （让模型列的 default 值生效）
            instance = self._model(**schema.model_dump(exclude_unset=True))
            self.session.add(instance)
            # flush 让数据库分配主键，使 ORM 实例获得自增 ID
            await self.session.flush()
            # refresh 从数据库拉回 server_default 字段（如 created_at），
            # 避免返回的实例缺少数据库侧生成的值
            await self.session.refresh(instance)
            return instance
        except IntegrityError as exc:
            # 唯一约束 / 外键约束冲突 → 业务可预期
            raise self._integrity_to_business(exc)
        except SQLAlchemyError as exc:
            # 其他数据库错误（连接断开、语法错误等）→ 原始错误透传
            raise DatabaseException(
                error_code=ErrorCode.DB_ERROR,
                message=f"{self._model.__name__} 创建失败",
                original_error=exc,
            )

    async def update(self, id: int, schema: Any) -> ModelType:
        """更新指定记录的部分字段。

        采用"先查后改"模式，确保对象存在再更新。
        只更新 schema 中实际设置的字段（exclude_unset），
        不会将 None 写回未传入的可选字段。

        参数:
            id: 要更新的记录主键
            schema: 更新请求 DTO 实例（_update_schema）

        返回:
            更新后的 ORM 模型实例

        异常:
            DatabaseException: 当记录不存在或违反约束时
        """
        # 先查询，不存在则抛 NOT_FOUND（用 _require_by_id 保留异常语义）
        instance = await self._require_by_id(id)

        # 只对 schema 中显式设置的字段做更新（exclude_unset），
        # 允许将可空字段显式设为 None（不传 exclude_none）
        update_data = schema.model_dump(exclude_unset=True)
        for field_name, value in update_data.items():
            setattr(instance, field_name, value)

        try:
            await self.session.flush()
            # refresh 从数据库拉回 server_onupdate 字段（如 updated_at），
            # 确保返回的实例反映数据库侧生成的最新值
            await self.session.refresh(instance)
            return instance
        except IntegrityError as exc:
            # 唯一约束 / 外键约束冲突 → 业务可预期
            raise self._integrity_to_business(exc)
        except SQLAlchemyError as exc:
            # 其他数据库错误（连接断开、语法错误等）→ 原始错误透传
            raise DatabaseException(
                error_code=ErrorCode.DB_ERROR,
                message=f"{self._model.__name__} 更新失败",
                original_error=exc,
            )

    async def delete(self, id: int) -> None:
        """删除指定记录。

        参数:
            id: 要删除的记录主键

        异常:
            DatabaseException: 当记录不存在或删除触发外键约束时
        """
        # 先查询确保对象存在（delete 必须拿到 ORM 实例才能删除）
        instance = await self._require_by_id(id)
        try:
            await self.session.delete(instance)
            await self.session.flush()
        except IntegrityError as exc:
            # 删除时违反约束（如有子记录引用）
            raise self._integrity_to_business(exc)
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_ERROR,
                message=f"{self._model.__name__} 删除失败",
                original_error=exc,
            )

    # —— ORM ↔ Schema 转换工具 ——

    def to_response(self, instance: ModelType) -> Any:
        """将 ORM 实例转换为简要响应 DTO。

        使用子类声明的 _response_schema 进行验证转换。

        参数:
            instance: ORM 模型实例

        返回:
            对应的响应 DTO 实例
        """
        return self._response_schema.model_validate(instance)

    def to_response_list(self, instances: list[ModelType]) -> list[Any]:
        """将 ORM 实例列表批量转换为简要响应 DTO 列表。

        参数:
            instances: ORM 模型实例列表

        返回:
            对应的响应 DTO 实例列表
        """
        return [self.to_response(inst) for inst in instances]

    # —— 内部工具 ——

    def _integrity_to_business(self, exc: IntegrityError) -> DatabaseException:
        """将 SQLAlchemy IntegrityError 转换为合适的 DatabaseException。

        根据异常类型和消息判断是唯一约束冲突还是外键约束冲突。
        """
        raw_msg = str(exc).lower()

        if "unique" in raw_msg or "duplicate" in raw_msg or "uq_" in raw_msg:
            return DatabaseException(
                error_code=ErrorCode.DB_UNIQUE_CONFLICT,
                message=f"{self._model.__name__} 的数据已存在，违反唯一约束",
                original_error=exc,
            )
        if "foreign key" in raw_msg or "fk_" in raw_msg:
            return DatabaseException(
                error_code=ErrorCode.DB_FK_CONFLICT,
                message=f"{self._model.__name__} 关联的数据不存在，违反外键约束",
                original_error=exc,
            )
        # 兜底：其他完整性错误
        return DatabaseException(
            error_code=ErrorCode.DB_ERROR,
            message=f"{self._model.__name__} 数据库完整性错误",
            original_error=exc,
        )
