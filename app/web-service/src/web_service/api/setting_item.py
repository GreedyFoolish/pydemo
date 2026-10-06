"""系统配置项的RESTful API路由

提供配置项的查询和更新操作：
- PUT    /settings/items                  按key批量更新配置值
- GET    /settings/items/all              获取所有配置项（包含组信息）
- GET    /settings/items/group/{group_id} 获取指定配置组下的所有配置项
- GET    /settings/items/{id}             根据ID获取配置项
- GET    /settings/items/filter           按条件过滤
- PUT    /settings/items/{id}             根据ID更新
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.core.database import get_session
from web_service.exception import DatabaseException, ErrorCode
from web_service.schema.setting_item import (
    SettingItemUpdate,
    SettingItemResponse,
    SettingItemAllResponse,
)
from web_service.service.setting_item import SettingItemService

router = APIRouter(prefix="/api/settings/items", tags=["系统配置项"])


@router.put(
    "",
    response_model=list[SettingItemResponse],
    summary="批量更新配置项",
    description="按 key 批量更新配置项的 value，用于系统设置页面保存。",
)
async def update_settings(
    data: list[SettingItemUpdate],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[SettingItemResponse]:
    service = SettingItemService(db)
    return await service.update_settings(data)


@router.get(
    "/all",
    response_model=SettingItemAllResponse,
    summary="获取所有配置项",
    description="获取所有配置项（包含所属组信息），用于前端配置管理页面。",
)
async def get_all_setting_items(
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SettingItemAllResponse:
    service = SettingItemService(db)
    return await service.list_all_with_group()


@router.get(
    "/group/{group_id}",
    response_model=list[SettingItemResponse],
    summary="获取指定配置组下的所有配置项",
    description="根据配置组ID获取该组下的所有配置项。",
)
async def list_setting_items_by_group(
    group_id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[SettingItemResponse]:
    service = SettingItemService(db)
    return await service.list_by_group(group_id)


@router.get(
    "/{id}",
    response_model=SettingItemResponse,
    summary="获取配置项详情",
    description="根据ID获取配置项。",
)
async def get_setting_item(
    id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SettingItemResponse:
    service = SettingItemService(db)
    instance = await service.get_by_id(id)
    if instance is None:
        raise DatabaseException(
            error_code=ErrorCode.NOT_FOUND,
            message="配置项不存在",
            detail=f"model=SettingItem, id={id}",
        )
    return service.to_response(instance)


@router.get(
    "/filter/",
    response_model=list[SettingItemResponse],
    summary="过滤查询配置项",
    description="按配置组ID、key等条件过滤配置项。",
)
async def filter_setting_items(
    db: Annotated[AsyncSession, Depends(get_session)],
    group_id: int | None = Query(default=None, description="配置组ID"),
    key: str | None = Query(default=None, description="配置项key"),
) -> list[SettingItemResponse]:
    service = SettingItemService(db)
    return await service.list_by_filter(group_id=group_id, key=key)


@router.put(
    "/{id}",
    response_model=SettingItemResponse,
    summary="更新配置项",
    description="根据ID更新配置项的字段（部分更新，未传入的字段保持不变）。",
)
async def update_setting_item(
    id: int,
    data: SettingItemUpdate,
    db: Annotated[AsyncSession, Depends(get_session)],
) -> SettingItemResponse:
    service = SettingItemService(db)
    instance = await service.update(id, data)
    return service.to_response(instance)
