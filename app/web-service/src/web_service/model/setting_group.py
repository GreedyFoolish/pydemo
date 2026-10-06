from typing import TYPE_CHECKING
from sqlalchemy import String, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from web_service.model.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    from web_service.model.setting_item import SettingItem


class SettingGroup(Base, IDMixin, TimestampMixin):
    """系统设置分组。

    用于将系统设置项按功能域归类，例如"基础设置"、"上传配置"等。
    与 SettingItem 是一对多关系：一个分组下可以有多个设置项。
    """

    # 分组唯一标识，用于代码中引用，如 "upload", "basic"
    key: Mapped[str] = mapped_column(String(100), unique=True)
    # 前端展示名称
    display_name: Mapped[str] = mapped_column(String(200))
    # 分组描述
    description: Mapped[str] = mapped_column(Text, default="")
    # 排序序号，用于显示排序
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # 是否启用
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # 关联到本组中的配置项
    items: Mapped[list["SettingItem"]] = relationship(
        back_populates="group", passive_deletes=True
    )
