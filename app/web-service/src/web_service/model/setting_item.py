from typing import TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from web_service.model.base import Base, IDMixin

if TYPE_CHECKING:
    from web_service.model.setting_group import SettingGroup


class SettingItem(Base, IDMixin):
    """具体的系统设置项。

    每个设置项归属一个 SettingGroup，同一分组内 key 不可重复（通过 UniqueConstraint(group_id, key) 保证）。
    """

    # 外键关联到 SettingGroup，删除分组时级联删除其下所有设置项
    group_id: Mapped[int] = mapped_column(
        ForeignKey("settinggroup.id", ondelete="CASCADE")
    )
    # 设置项在分组内的唯一标识
    key: Mapped[str] = mapped_column(String(100))
    # 设置值
    value: Mapped[str] = mapped_column(Text, default="")
    # 前端展示名称
    display_name: Mapped[str] = mapped_column(String(200))
    # 设置项描述
    description: Mapped[str] = mapped_column(Text, default="")

    # 多对一关系：setting_item.group → 所属分组
    group: Mapped["SettingGroup"] = relationship(back_populates="items")

    # 联合唯一约束：同一分组内 key 不可重复
    __table_args__ = (
        UniqueConstraint("group_id", "key", name="uq_setting_item_group_key"),
    )
