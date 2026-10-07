"""系统配置项的Service实现

继承BaseService[SettingItem]，提供配置项特有的业务方法，并负责启动时的种子数据初始化。
"""

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from web_service.exception import DatabaseException, ErrorCode
from web_service.model.setting_group import SettingGroup
from web_service.model.setting_item import SettingItem
from web_service.seed.settings_seed import SETTING_SEEDS
from web_service.service.base import BaseService
from web_service.schema.setting_item import (
    SettingItemUpdate,
    SettingItemResponse,
    SettingItemWithGroupResponse,
    SettingGroupSimpleResponse,
    SettingItemAllResponse,
)


class SettingItemService(BaseService[SettingItem]):
    """配置项的业务服务

    只提供查询和更新操作，不提供创建和删除。
    """

    _model = SettingItem
    _create_schema = None  # 不支持创建
    _update_schema = SettingItemUpdate
    _response_schema = SettingItemResponse

    async def init_settings(self) -> None:
        """启动时自动初始化系统配置种子数据。

        幂等执行：
        - SettingGroup 按 key 查找，缺失则创建
        - SettingItem 按 (group_id, key) 查找，缺失则创建
        - 已存在的 SettingItem.value **不会**被覆盖
          （用户可能已通过 UI 修改过配置值）
        - 已存在的 SettingGroup / SettingItem 的 display_name / description
          会与种子数据保持同步

        事务由外部（lifespan 或 CLI 调用方）控制 commit。
        """
        # —— Step 1: 确保所有 SettingGroup 存在 ——
        # 先把所有现有 group 查出来，减少 N+1
        existing_groups_stmt = select(SettingGroup)
        result = await self.session.execute(existing_groups_stmt)
        existing_groups = {g.key: g for g in result.scalars().all()}

        group_id_map: dict[str, int] = {}  # key → db id

        for group_seed in SETTING_SEEDS:
            group = existing_groups.get(group_seed.key)
            if group is None:
                # 新增
                group = SettingGroup(
                    key=group_seed.key,
                    display_name=group_seed.display_name,
                    description=group_seed.description,
                    sort_order=group_seed.sort_order,
                    is_active=group_seed.is_active,
                )
                self.session.add(group)
                logger.info("创建配置组: key=%s", group_seed.key)
            else:
                # 已存在：同步元信息（不影响 value 相关）
                if group.display_name != group_seed.display_name:
                    group.display_name = group_seed.display_name
                if group.description != group_seed.description:
                    group.description = group_seed.description
                if group.sort_order != group_seed.sort_order:
                    group.sort_order = group_seed.sort_order
                if group.is_active != group_seed.is_active:
                    group.is_active = group_seed.is_active

        # flush 让 group 拿到自增 ID，然后重新 select 建立完整的 key → id 映射
        await self.session.flush()
        refreshed = await self.session.execute(select(SettingGroup))
        group_id_map: dict[str, int] = {g.key: g.id for g in refreshed.scalars().all()}

        # —— Step 2: 确保所有 SettingItem 存在 ——
        # 查所有已存在的 item，按 (group_id, key) 索引
        existing_items_stmt = select(SettingItem)
        result = await self.session.execute(existing_items_stmt)
        existing_items: dict[tuple[int, str], SettingItem] = {
            (item.group_id, item.key): item for item in result.scalars().all()
        }

        new_items_count = 0
        for group_seed in SETTING_SEEDS:
            group_id = group_id_map[group_seed.key]
            for item_seed in group_seed.items:
                key = (group_id, item_seed.key)
                item = existing_items.get(key)
                if item is None:
                    # 新增，value 使用种子默认值
                    item = SettingItem(
                        group_id=group_id,
                        key=item_seed.key,
                        display_name=item_seed.display_name,
                        description=item_seed.description,
                        value=item_seed.value,
                    )
                    self.session.add(item)
                    new_items_count += 1
                    logger.info(
                        "创建配置项: group=%s key=%s",
                        group_seed.key,
                        item_seed.key,
                    )
                else:
                    # 已存在：同步 display_name / description，**不碰 value**
                    if item.display_name != item_seed.display_name:
                        item.display_name = item_seed.display_name
                    if item.description != item_seed.description:
                        item.description = item_seed.description

        if new_items_count > 0:
            await self.session.flush()
        logger.info("系统配置初始化完成，新增配置项 %d 个", new_items_count)

    async def list_all_with_group(self) -> SettingItemAllResponse:
        """获取所有配置项（包含所属组信息），用于前端配置管理页面"""
        try:
            # 查询所有配置项，预加载关联的组
            stmt = (
                select(SettingItem)
                .options(selectinload(SettingItem.group))
                .order_by(SettingItem.group_id.asc(), SettingItem.id.asc())
            )
            result = await self.session.execute(stmt)
            items = list(result.unique().scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message="配置项全量查询失败",
                original_error=exc,
            )

        # 转换为包含组信息的响应
        item_responses = []
        for item in items:
            group_resp = SettingGroupSimpleResponse.model_validate(item.group)
            item_resp = SettingItemWithGroupResponse(
                id=item.id,
                group_id=item.group_id,
                key=item.key,
                display_name=item.display_name,
                description=item.description,
                value=item.value,
                group=group_resp,
            )
            item_responses.append(item_resp)

        return SettingItemAllResponse(
            items=item_responses,
            total_count=len(item_responses),
        )

    async def update_settings(
        self, data: list[SettingItemUpdate]
    ) -> list[SettingItemResponse]:
        """按 key 批量更新配置项的 value。

        仅更新显式传入 value 的项；按业务键 key 匹配（本项目 key 在业务上全局唯一）。

        参数:
            data: SettingItemUpdate 列表，使用其中的 key / value 字段

        返回:
            被更新的配置项响应列表

        异常:
            DatabaseException: 当数据库执行出错时（code=DB_OPERATIONAL_ERROR）
        """
        update_map = {item.key: item.value for item in data if item.key is not None}
        if not update_map:
            return []

        try:
            stmt = select(SettingItem).where(SettingItem.key.in_(update_map.keys()))
            result = await self.session.execute(stmt)
            instances = list(result.scalars().all())

            for instance in instances:
                if update_map[instance.key] is not None:
                    instance.value = update_map[instance.key]

            await self.session.flush()
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message="配置项批量更新失败",
                original_error=exc,
            )
        return self.to_response_list(instances)

    async def list_by_group(self, group_id: int) -> list[SettingItemResponse]:
        """获取指定配置组下的所有配置项"""
        try:
            stmt = (
                select(SettingItem)
                .where(SettingItem.group_id == group_id)
                .order_by(SettingItem.id.asc())
            )
            result = await self.session.execute(stmt)
            instances = list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message="配置项列表查询失败",
                original_error=exc,
            )
        return self.to_response_list(instances)

    async def list_by_filter(
        self,
        group_id: int | None = None,
        key: str | None = None,
    ) -> list[SettingItemResponse]:
        """按条件过滤配置项"""
        try:
            stmt = select(SettingItem).order_by(SettingItem.id.asc())
            if group_id is not None:
                stmt = stmt.where(SettingItem.group_id == group_id)
            if key is not None:
                stmt = stmt.where(SettingItem.key == key)
            result = await self.session.execute(stmt)
            instances = list(result.scalars().all())
        except SQLAlchemyError as exc:
            raise DatabaseException(
                error_code=ErrorCode.DB_OPERATIONAL_ERROR,
                message="配置项过滤查询失败",
                original_error=exc,
            )
        return self.to_response_list(instances)
