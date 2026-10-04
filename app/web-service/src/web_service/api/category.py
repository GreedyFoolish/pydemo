"""
Category 实体的 RESTful API 路由。

提供分类的完整 CRUD 操作：
- POST   /categories          新增分类
- GET    /categories          列表查询（分页）
- GET    /categories/{id}     根据 ID 获取详情（含关联产品）
- PUT    /categories/{id}     根据 ID 更新
- DELETE /categories/{id}     根据 ID 删除
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.core.database import get_session
from web_service.exception import DatabaseException, ErrorCode
from web_service.schema.category import (
    CategoryCreate,
    CategoryResponse,
    CategoryResponseDetail,
    CategoryUpdate,
)
from web_service.service.base import PageResult
from web_service.service.category import CategoryService

router = APIRouter(prefix="/api/categories", tags=["分类管理"])


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增分类",
    description="创建一个新的分类记录。",
)
async def create_category(
    data: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CategoryResponse:
    service = CategoryService(db)
    instance = await service.create(data)
    return service.to_response(instance)


@router.get(
    "",
    response_model=PageResult[CategoryResponse],
    summary="分类列表（分页）",
    description="分页查询分类列表，支持按任意字段排序。",
)
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页条数"),
    order_by: str = Query(default="id", description="排序字段（模型列名）"),
    ascending: bool = Query(default=True, description="True 升序，False 降序"),
) -> PageResult[CategoryResponse]:
    service = CategoryService(db)
    return await service.list_paged(
        page=page, page_size=page_size, order_by=order_by, ascending=ascending
    )


@router.get(
    "/{id}",
    response_model=CategoryResponseDetail,
    summary="获取分类详情",
    description="根据 ID 获取分类详情，包含其下所有关联产品。",
)
async def get_category(
    id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CategoryResponseDetail:
    service = CategoryService(db)
    detail = await service.get_detail(id)
    if detail is None:
        raise DatabaseException(
            error_code=ErrorCode.NOT_FOUND,
            message=f"分类不存在",
            detail=f"model=Category, id={id}",
        )
    return detail


@router.put(
    "/{id}",
    response_model=CategoryResponse,
    summary="更新分类",
    description="根据 ID 更新分类的部分字段（部分更新语义，未传入的字段保持不变）。",
)
async def update_category(
    id: int,
    data: CategoryUpdate,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CategoryResponse:
    service = CategoryService(db)
    instance = await service.update(id, data)
    return service.to_response(instance)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除分类",
    description="根据 ID 删除分类记录。",
)
async def delete_category(
    id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    service = CategoryService(db)
    await service.delete(id)
    return None
