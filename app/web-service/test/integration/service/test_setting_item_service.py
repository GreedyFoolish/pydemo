"""
SettingItem Service 集成测试。

直接调用 SettingItemService（通过 db_session fixture），
覆盖：
- init_settings 种子初始化（幂等性、value 保护、metadata 同步）
- list_all_with_group / list_by_group / list_by_filter / get_by_id
- update（只允许改 value / display_name / description，key 不可修改）
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.exception import DatabaseException, ErrorCode
from web_service.model.setting_group import SettingGroup
from web_service.model.setting_item import SettingItem
from web_service.schema.setting_item import SettingItemUpdate
from web_service.seed.settings_seed import SETTING_SEEDS
from web_service.service.setting_item import SettingItemService


async def _init_and_commit(db_session: AsyncSession, service: SettingItemService):
    """初始化种子数据并 commit，供需要数据的测试用例使用。"""
    await service.init_settings()
    await db_session.commit()


# ═══════════════════════════════════════════════════════════════════
# init_settings 种子初始化测试
# ═══════════════════════════════════════════════════════════════════


class TestInitSettings:
    """init_settings 幂等性与保护性语义测试。"""

    @pytest.mark.smoke
    async def test_first_run_creates_all_seeds(self, db_session: AsyncSession):
        """首次运行：空库时创建所有种子 group 和 item。"""
        from sqlalchemy import select

        service = SettingItemService(db_session)
        await service.init_settings()
        await db_session.commit()

        # 验证种子 group 和 item 都创建了（数量与种子定义一致）
        groups = (await db_session.execute(select(SettingGroup))).scalars().all()
        assert len(groups) == len(SETTING_SEEDS)
        group_keys = {g.key for g in groups}
        assert group_keys == {g.key for g in SETTING_SEEDS}

        total_seed_items = sum(len(g.items) for g in SETTING_SEEDS)
        items = (await db_session.execute(select(SettingItem))).scalars().all()
        assert len(items) == total_seed_items

    async def test_idempotent_second_run_no_duplicates(
        self, db_session: AsyncSession
    ):
        """第二次运行：已存在的不重复创建。"""
        service = SettingItemService(db_session)

        # 首次
        await service.init_settings()
        await db_session.commit()

        count_before = await service.count()

        # 第二次
        await service.init_settings()
        await db_session.commit()

        count_after = await service.count()
        assert count_before == count_after  # 数量不变

    async def test_user_modified_value_preserved(self, db_session: AsyncSession):
        """用户改过的 value 不会被种子初始化覆盖。"""
        from sqlalchemy import select

        service = SettingItemService(db_session)

        # 首次
        await service.init_settings()
        await db_session.commit()

        # 动态拿第一个 item，修改它的 value
        first_item = (
            (await db_session.execute(select(SettingItem)))
            .scalars()
            .first()
        )
        original_key = first_item.key
        first_item.value = "用户自定义值"
        await db_session.commit()

        # 再次初始化
        await service.init_settings()
        await db_session.commit()

        # 验证用户修改的 value 还在
        stmt = select(SettingItem).where(SettingItem.key == original_key)
        item_after = (await db_session.execute(stmt)).scalar_one()
        assert item_after.value == "用户自定义值"

    async def test_metadata_synced_on_reinit(self, db_session: AsyncSession):
        """display_name / description / sort_order / is_active 会与种子同步。"""
        from sqlalchemy import select

        service = SettingItemService(db_session)
        await service.init_settings()
        await db_session.commit()

        # 动态拿第一个 group，改坏它的 metadata
        first_group = (
            (await db_session.execute(select(SettingGroup).order_by(SettingGroup.id.asc())))
            .scalars()
            .first()
        )
        seed_group = next(g for g in SETTING_SEEDS if g.key == first_group.key)

        first_group.display_name = "坏名字"
        first_group.sort_order = 99
        first_group.is_active = False
        await db_session.commit()

        # 再次初始化
        await service.init_settings()
        await db_session.commit()

        # 验证被同步回种子定义
        first_group = (
            (await db_session.execute(select(SettingGroup).where(SettingGroup.key == seed_group.key)))
            .scalar_one()
        )
        assert first_group.display_name == seed_group.display_name
        assert first_group.sort_order == seed_group.sort_order
        assert first_group.is_active == seed_group.is_active

    async def test_new_seed_items_added(self, db_session: AsyncSession):
        """种子文件新增的 item 会被补齐到数据库。"""
        from sqlalchemy import select

        service = SettingItemService(db_session)
        await service.init_settings()
        await db_session.commit()

        # 动态拿第一个有 item 的 group，删掉它的第一个 item
        first_with_items = next(g for g in SETTING_SEEDS if len(g.items) > 0)
        db_group = (
            (await db_session.execute(select(SettingGroup).where(SettingGroup.key == first_with_items.key)))
            .scalar_one()
        )
        first_seed_item_key = first_with_items.items[0].key
        stmt = select(SettingItem).where(
            SettingItem.group_id == db_group.id,
            SettingItem.key == first_seed_item_key,
        )
        item = (await db_session.execute(stmt)).scalar_one()
        original_count = await service.count()
        await db_session.delete(item)
        await db_session.commit()

        # 再次初始化，应该把删掉的 item 补回来
        await service.init_settings()
        await db_session.commit()

        count_after = await service.count()
        assert count_after == original_count


# ═══════════════════════════════════════════════════════════════════
# 查询方法测试
# ═══════════════════════════════════════════════════════════════════


class TestSettingItemServiceListAllWithGroup:
    """list_all_with_group 全量查询带组信息。"""

    async def test_returns_all_items_with_group(self, db_session: AsyncSession):
        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        total_seed_items = sum(len(g.items) for g in SETTING_SEEDS)
        resp = await service.list_all_with_group()
        assert resp.total_count == total_seed_items
        assert len(resp.items) == total_seed_items

        # 每个 item 都带 group 信息
        for item in resp.items:
            assert item.group is not None
            assert item.group.id is not None
            assert item.group.key is not None

        # 按 group_id.asc() 排序（service 实现约定）
        group_ids = [item.group_id for item in resp.items]
        assert group_ids == sorted(group_ids)

    async def test_empty_when_no_data(self, db_session: AsyncSession):
        """空库时返回空结构。"""
        service = SettingItemService(db_session)
        resp = await service.list_all_with_group()
        assert resp.total_count == 0
        assert resp.items == []


class TestSettingItemServiceListByGroup:
    """list_by_group 按组查询。"""

    async def test_returns_items_for_group(self, db_session: AsyncSession):
        from sqlalchemy import select

        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        # 动态拿第一个种子 group
        first_seed_group = SETTING_SEEDS[0]
        db_group = (
            (await db_session.execute(select(SettingGroup).where(SettingGroup.key == first_seed_group.key)))
            .scalar_one()
        )

        items = await service.list_by_group(db_group.id)
        assert len(items) == len(first_seed_group.items)
        expected_keys = {i.key for i in first_seed_group.items}
        assert {i.key for i in items} == expected_keys

    async def test_empty_when_group_not_found(self, db_session: AsyncSession):
        """不存在的 group_id 返回空列表（不会报错）。"""
        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        items = await service.list_by_group(9999)
        assert items == []


class TestSettingItemServiceListByFilter:
    """list_by_filter 过滤查询。"""

    async def test_filter_by_key(self, db_session: AsyncSession):
        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        # 动态拿第一个种子 item 的 key
        first_item_key = SETTING_SEEDS[0].items[0].key

        items = await service.list_by_filter(key=first_item_key)
        assert len(items) == 1
        assert items[0].key == first_item_key

    async def test_filter_by_group_id(self, db_session: AsyncSession):
        from sqlalchemy import select

        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        first_seed_group = SETTING_SEEDS[0]
        db_group = (
            (await db_session.execute(select(SettingGroup).where(SettingGroup.key == first_seed_group.key)))
            .scalar_one()
        )
        items = await service.list_by_filter(group_id=db_group.id)
        assert len(items) == len(first_seed_group.items)

    async def test_filter_both(self, db_session: AsyncSession):
        from sqlalchemy import select

        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        first_seed_group = SETTING_SEEDS[0]
        first_item = first_seed_group.items[0]
        db_group = (
            (await db_session.execute(select(SettingGroup).where(SettingGroup.key == first_seed_group.key)))
            .scalar_one()
        )
        items = await service.list_by_filter(
            group_id=db_group.id, key=first_item.key
        )
        assert len(items) == 1
        assert items[0].key == first_item.key

    async def test_filter_no_match(self, db_session: AsyncSession):
        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        items = await service.list_by_filter(key="nonexistent_key_xyz")
        assert items == []


class TestSettingItemServiceGetById:
    """get_by_id 测试（继承 BaseService）。"""

    async def test_found(self, db_session: AsyncSession):
        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        from sqlalchemy import select

        item = (await db_session.execute(select(SettingItem))).scalars().first()

        found = await service.get_by_id(item.id)
        assert found is not None
        assert found.id == item.id

    async def test_not_found(self, db_session: AsyncSession):
        service = SettingItemService(db_session)
        assert await service.get_by_id(9999) is None


# ═══════════════════════════════════════════════════════════════════
# update 方法测试
# ═══════════════════════════════════════════════════════════════════


class TestSettingItemServiceUpdate:
    """update 部分更新语义测试。"""

    async def test_update_value_only(self, db_session: AsyncSession):
        from sqlalchemy import select

        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        item = (await db_session.execute(select(SettingItem))).scalars().first()
        new_value = "新值"

        updated = await service.update(item.id, SettingItemUpdate(value=new_value))
        await db_session.commit()

        assert updated.value == "新值"
        # 其他字段保持不变
        assert updated.key == item.key
        assert updated.display_name == item.display_name

    async def test_update_display_name(self, db_session: AsyncSession):
        from sqlalchemy import select

        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        item = (await db_session.execute(select(SettingItem))).scalars().first()

        updated = await service.update(
            item.id, SettingItemUpdate(display_name="新显示名")
        )
        await db_session.commit()

        assert updated.display_name == "新显示名"
        assert updated.value == item.value  # value 不变

    async def test_update_preserves_key(self, db_session: AsyncSession):
        """SettingItemUpdate 不含 key 字段，验证 schema 层已移除。"""
        # 直接断言 SettingItemUpdate 的 model 里没有 key
        schema_fields = SettingItemUpdate.model_fields
        assert "key" not in schema_fields

    async def test_update_not_found(self, db_session: AsyncSession):
        service = SettingItemService(db_session)
        await _init_and_commit(db_session, service)

        with pytest.raises(DatabaseException) as exc_info:
            await service.update(9999, SettingItemUpdate(value="不存在"))

        assert exc_info.value.error_code == ErrorCode.NOT_FOUND
