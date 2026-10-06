"""SettingItem Schema 单元测试。

覆盖 SettingItemUpdate / SettingItemResponse / SettingItemFilter
/ SettingItemWithGroupResponse / SettingGroupSimpleResponse
/ SettingItemAllResponse 的字段约束、默认值、嵌套结构。
"""

import pytest
from pydantic import ValidationError

from web_service.schema.setting_item import (
    SettingItemUpdate,
    SettingItemResponse,
    SettingItemFilter,
    SettingItemWithGroupResponse,
    SettingGroupSimpleResponse,
    SettingItemAllResponse,
)

# ============================================================
# SettingItemUpdate 测试
# ============================================================


class TestSettingItemUpdate:
    """SettingItemUpdate 部分更新请求测试。"""

    def test_all_none_is_valid(self):
        """所有字段为 None 合法（部分更新语义）。"""
        schema = SettingItemUpdate()
        assert schema.value is None
        assert schema.display_name is None
        assert schema.description is None

    def test_value_only(self):
        """只更新 value。"""
        schema = SettingItemUpdate(value="新值")
        assert schema.value == "新值"

    def test_display_name_too_short(self):
        """display_name 空串违反 min_length=1。"""
        with pytest.raises(ValidationError):
            SettingItemUpdate(display_name="")

    def test_display_name_too_long(self):
        """display_name 超过 200 字符失败。"""
        with pytest.raises(ValidationError):
            SettingItemUpdate(display_name="x" * 201)

    def test_display_name_boundary_max(self):
        """恰好 200 字符通过。"""
        schema = SettingItemUpdate(display_name="x" * 200)
        assert len(schema.display_name) == 200

    def test_description_too_long(self):
        """description 超过 2000 字符失败。"""
        with pytest.raises(ValidationError):
            SettingItemUpdate(description="x" * 2001)

    def test_description_boundary_max(self):
        """恰好 2000 字符通过。"""
        schema = SettingItemUpdate(description="x" * 2000)
        assert len(schema.description) == 2000

    def test_key_not_in_update_schema(self):
        """SettingItemUpdate 不应包含 key 字段（不可修改）。"""
        schema = SettingItemUpdate()
        assert not hasattr(schema, "key")

    def test_extra_fields_ignored(self):
        """多余字段被忽略。"""
        schema = SettingItemUpdate(value="v", unknown=1)
        assert not hasattr(schema, "unknown")


# ============================================================
# SettingItemResponse 测试
# ============================================================


class TestSettingItemResponse:
    """SettingItemResponse 响应测试。"""

    def test_valid_input(self):
        schema = SettingItemResponse(
            id=1, group_id=2, key="site_name", display_name="站点名"
        )
        assert schema.id == 1
        assert schema.group_id == 2
        assert schema.key == "site_name"

    def test_default_values(self):
        """缺省 value 和 description 为空串。"""
        schema = SettingItemResponse(id=1, group_id=2, key="k", display_name="d")
        assert schema.value == ""
        assert schema.description == ""

    def test_missing_required_fields(self):
        """缺少必填字段触发 ValidationError。"""
        with pytest.raises(ValidationError):
            SettingItemResponse(id=1)  # 缺 group_id / key / display_name

    def test_from_attributes(self):
        """测试 from_attributes=True，可从 ORM 实例构造。"""
        from unittest.mock import MagicMock

        orm = MagicMock()
        orm.id = 10
        orm.group_id = 5
        orm.key = "max_size"
        orm.display_name = "最大尺寸"
        orm.value = "100"
        orm.description = "描述"

        schema = SettingItemResponse.model_validate(orm)
        assert schema.id == 10
        assert schema.key == "max_size"
        assert schema.value == "100"


# ============================================================
# SettingItemFilter 测试
# ============================================================


class TestSettingItemFilter:
    """SettingItemFilter 过滤条件测试。"""

    def test_all_none(self):
        """所有条件为 None 合法。"""
        schema = SettingItemFilter()
        assert schema.group_id is None
        assert schema.key is None
        assert schema.is_active is None

    def test_with_group_id(self):
        schema = SettingItemFilter(group_id=3)
        assert schema.group_id == 3

    def test_with_key(self):
        schema = SettingItemFilter(key="upload")
        assert schema.key == "upload"

    def test_with_is_active(self):
        schema = SettingItemFilter(is_active=False)
        assert schema.is_active is False


# ============================================================
# SettingGroupSimpleResponse 测试
# ============================================================


class TestSettingGroupSimpleResponse:
    """SettingGroupSimpleResponse（嵌套在 item 响应中）测试。"""

    def test_valid_input(self):
        schema = SettingGroupSimpleResponse(id=1, key="basic", display_name="基础设置")
        assert schema.id == 1
        assert schema.key == "basic"

    def test_default_values(self):
        """description 缺省为空串，is_active 缺省为 True。"""
        schema = SettingGroupSimpleResponse(id=1, key="basic", display_name="基础设置")
        assert schema.description == ""
        assert schema.is_active is True


# ============================================================
# SettingItemWithGroupResponse 测试
# ============================================================


class TestSettingItemWithGroupResponse:
    """SettingItemWithGroupResponse 嵌套 group 信息的响应测试。"""

    def test_with_group(self):
        group = SettingGroupSimpleResponse(id=1, key="basic", display_name="基础设置")
        item = SettingItemWithGroupResponse(
            id=10,
            group_id=1,
            key="site_name",
            display_name="站点名称",
            group=group,
        )
        assert item.group is not None
        assert item.group.key == "basic"

    def test_group_none_default(self):
        """group 缺省为 None。"""
        item = SettingItemWithGroupResponse(
            id=10, group_id=1, key="k", display_name="d"
        )
        assert item.group is None

    def test_from_attributes_with_nested_group(self):
        """from_attributes=True 对嵌套 group 也生效。"""
        from unittest.mock import MagicMock

        orm_item = MagicMock()
        orm_item.id = 10
        orm_item.group_id = 1
        orm_item.key = "k"
        orm_item.display_name = "d"
        orm_item.value = "v"
        orm_item.description = ""
        orm_item.group = MagicMock()
        orm_item.group.id = 1
        orm_item.group.key = "basic"
        orm_item.group.display_name = "基础设置"
        orm_item.group.description = ""
        orm_item.group.is_active = True

        schema = SettingItemWithGroupResponse.model_validate(orm_item)
        assert schema.group.key == "basic"


# ============================================================
# SettingItemAllResponse 测试
# ============================================================


class TestSettingItemAllResponse:
    """SettingItemAllResponse 全量配置项响应测试。"""

    def test_default_empty(self):
        """items 缺省为空列表，total_count 缺省为 0。"""
        schema = SettingItemAllResponse()
        assert schema.items == []
        assert schema.total_count == 0

    def test_with_items(self):
        group = SettingGroupSimpleResponse(id=1, key="basic", display_name="基础设置")
        item = SettingItemWithGroupResponse(
            id=10,
            group_id=1,
            key="site_name",
            display_name="站点名称",
            group=group,
        )
        schema = SettingItemAllResponse(items=[item], total_count=1)
        assert len(schema.items) == 1
        assert schema.total_count == 1
        assert schema.items[0].group.key == "basic"
