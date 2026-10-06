"""SettingItem 相关的 DTO 定义。

对应模型：web_service.model.setting_item.SettingItem
"""

from pydantic import Field
from web_service.schema.base import BaseSchema


class SettingItemUpdate(BaseSchema):
    """更新配置项的请求，所有字段都是可选的，支持部分更新

    key 是配置项的业务标识，一旦建立不可修改；
    display_name / description / value 允许调整。
    """

    value: str | None = Field(default=None, description="配置值")
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class SettingItemResponse(BaseSchema):
    """配置项的响应数据"""

    id: int
    group_id: int
    key: str
    value: str = ""
    display_name: str
    description: str = ""


class SettingItemFilter(BaseSchema):
    """配置项的查询过滤条件"""

    group_id: int | None = Field(default=None, description="配置组ID")
    key: str | None = Field(default=None, description="配置项key")
    is_active: bool | None = Field(default=None, description="是否启用")


class SettingItemWithGroupResponse(BaseSchema):
    """配置项响应数据，包含所属配置组信息"""

    id: int
    group_id: int
    key: str
    value: str = ""
    display_name: str
    description: str = ""
    group: "SettingGroupSimpleResponse" = None


class SettingGroupSimpleResponse(BaseSchema):
    """配置组简化响应数据，用于配置项中的关联信息"""

    id: int
    key: str
    display_name: str
    description: str = ""
    is_active: bool = True


class SettingItemAllResponse(BaseSchema):
    """所有配置项的响应数据，用于前端配置管理页面"""

    items: list["SettingItemWithGroupResponse"] = []
    total_count: int = 0
