"""
Sku 实体的 RESTful API 路由。

提供 SKU 的完整 CRUD 操作：
- POST   /skus                新增 SKU
- GET    /skus                列表查询（分页）
- GET    /skus/{id}           根据 ID 获取详情（含所属产品）
- PUT    /skus/{id}           根据 ID 更新
- DELETE /skus/{id}           根据 ID 删除
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.core.database import get_session
from web_service.exception import DatabaseException, ErrorCode
from web_service.schema.sku import (
    SkuCreate,
    SkuResponse,
    SkuResponseDetail,
    SkuUpdate,
)
from web_service.service.base import PageResult
from web_service.service.sku import SkuService

router = APIRouter(prefix="/api/skus", tags=["SKU管理"])


@router.post(
    "",
    response_model=SkuResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增 SKU",
    description="创建一个新的 SKU，传入的 product_id 必须对应已存在的产品。",
)
async def create_sku(
    data: SkuCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SkuResponse:
    service = SkuService(db)
    instance = await service.create(data)
    return service.to_response(instance)


@router.get(
    "",
    response_model=PageResult[SkuResponse],
    summary="SKU 列表（分页）",
    description="分页查询 SKU 列表，支持按任意字段排序。",
)
async def list_skus(
    db: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    order_by: str = Query(default="id", description="排序字段（模型列名）"),
    ascending: bool = Query(default=True, description="True 升序，False 降序"),
) -> PageResult[SkuResponse]:
    service = SkuService(db)
    return await service.list_paged(
        page=page, page_size=page_size, order_by=order_by, ascending=ascending
    )


@router.get(
    "/{id}",
    response_model=SkuResponseDetail,
    summary="获取 SKU 详情",
    description="根据 ID 获取 SKU 详情，包含所属产品信息。",
)
async def get_sku(
    id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SkuResponseDetail:
    service = SkuService(db)
    detail = await service.get_detail(id)
    if detail is None:
        raise DatabaseException(
            error_code=ErrorCode.NOT_FOUND,
            message=f"SKU 不存在",
            detail=f"model=Sku, id={id}",
        )
    return detail


@router.put(
    "/{id}",
    response_model=SkuResponse,
    summary="更新 SKU",
    description="根据 ID 更新 SKU 的部分字段（部分更新语义，未传入的字段保持不变）。",
)
async def update_sku(
    id: int,
    data: SkuUpdate,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SkuResponse:
    service = SkuService(db)
    instance = await service.update(id, data)
    return service.to_response(instance)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除 SKU",
    description="根据 ID 删除 SKU 记录。",
)
async def delete_sku(
    id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    service = SkuService(db)
    await service.delete(id)
    return None
