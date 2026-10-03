"""
Product 实体的 RESTful API 路由。

提供产品的完整 CRUD 操作：
- POST   /products            新增产品（含分类关联）
- GET    /products            列表查询（分页）
- GET    /products/{id}       根据 ID 获取详情（含分类和 SKU）
- PUT    /products/{id}       根据 ID 更新（含分类关联更新）
- DELETE /products/{id}       根据 ID 删除
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.core.database import get_session
from web_service.exception import BusinessException, ErrorCode
from web_service.schema.product import (
    ProductCreate,
    ProductResponse,
    ProductResponseDetail,
    ProductUpdate,
)
from web_service.service.base import PageResult
from web_service.service.product import ProductService

router = APIRouter(prefix="/api/products", tags=["产品管理"])


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增产品",
    description="创建一个新产品，可同时传入 category_ids 建立多对多关联。",
)
async def create_product(
    data: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ProductResponse:
    service = ProductService(db)
    instance = await service.create(data)
    return service.to_response(instance)


@router.get(
    "",
    response_model=PageResult[ProductResponse],
    summary="产品列表（分页）",
    description="分页查询产品列表，支持按任意字段排序。",
)
async def list_products(
    db: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    order_by: str = Query(default="id", description="排序字段（模型列名）"),
    ascending: bool = Query(default=True, description="True 升序，False 降序"),
) -> PageResult[ProductResponse]:
    service = ProductService(db)
    return await service.list_paged(
        page=page, page_size=page_size, order_by=order_by, ascending=ascending
    )


@router.get(
    "/{id}",
    response_model=ProductResponseDetail,
    summary="获取产品详情",
    description="根据 ID 获取产品详情，包含关联的分类和 SKU 列表。",
)
async def get_product(
    id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ProductResponseDetail:
    service = ProductService(db)
    detail = await service.get_detail(id)
    if detail is None:
        raise BusinessException(
            error_code=ErrorCode.NOT_FOUND,
            message=f"产品不存在（id={id}）",
            detail=f"model=Product, id={id}",
        )
    return detail


@router.put(
    "/{id}",
    response_model=ProductResponse,
    summary="更新产品",
    description="根据 ID 更新产品字段，若传入 category_ids 则同时更新分类关联（完全替换）。",
)
async def update_product(
    id: int,
    data: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> ProductResponse:
    service = ProductService(db)
    instance = await service.update(id, data)
    return service.to_response(instance)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除产品",
    description="根据 ID 删除产品记录。",
)
async def delete_product(
    id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    service = ProductService(db)
    await service.delete(id)
    return None
