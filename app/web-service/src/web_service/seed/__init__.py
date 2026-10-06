"""种子数据模块。

提供系统初始化所需的基础种子数据，启动时自动写入数据库。
"""

from web_service.seed.settings_seed import (
    SettingItemSeed,
    SettingGroupSeed,
    SETTING_SEEDS,
)

__all__ = [
    "SettingItemSeed",
    "SettingGroupSeed",
    "SETTING_SEEDS",
]
