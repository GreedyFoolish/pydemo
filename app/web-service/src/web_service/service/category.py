"""
Category 实体的 Service 实现。

继承 BaseService[Category]，提供 Category 特有的业务方法，
并覆盖子类声明所需的类属性。
"""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from web_service.exception import DatabaseException, ErrorCode
from web_service.model.category import Category
from web_service.service.base import BaseService
from web_service.schema.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryResponseDetail,
    CategoryUpdate,
)


class CategoryService(BaseService[Category]):
    """分类实体的业务服务。

    只需声明四个类属性，即可继承基类的全部通用 CRUD：
        get_by_id / list / count / create / update / delete

    额外提供 get_detail() 方法，返回包含关联产品的详细响应。
    """

    # —— 子类必须声明的类属性 ——
    _model = Category
    _create_schema = CategoryCreate
    _update_schema = CategoryUpdate
    _response_schema = CategoryResponse

    async def get_detail(self, id: int) -> CategoryResponseDetail | None:
        """获取分类详情，包含其下所有产品。

        使用 selectinload 预加载 products 关联，
        避免后续访问触发懒加载异常。

        参数:
            id: 分类主键

        返回:
            CategoryResponseDetail（包含 products 列表），不存在则返回 None

        异常:
            DatabaseException: 当数据库执行出错时
        """
        try:
            stmt = (
                select(Category)
                .options(selectinload(Category.products))
                .where(Category.id == id)
            )
            result = await self.session.execute(stmt)
            instance = result.unique().scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message=f"分类详情查询失败",
                original_error=exc,
            )

        if instance is None:
            return None

        return CategoryResponseDetail.model_validate(instance)
