"""系统设置的种子数据定义。

结构与 model 层保持一致：SettingGroup 包含 items 列表，
每个 SettingItem 归属于一个 group。字段命名镜像 ORM 模型，
方便 Service 层直接做 upsert 映射。

注意：本文件只负责定义"期望的数据结构"，
实际写入/更新逻辑在 service/setting_item.py 的 init_settings 中完成。
"""

from dataclasses import dataclass, field


@dataclass
class SettingItemSeed:
    """种子数据：单个配置项

    字段对应 model/setting_item.py 的非外键字段：
    key / display_name / description / value
    group_id 不在此处，由 SettingGroupSeed 嵌套结构体现归属关系。
    """

    # 配置项在分组内的唯一标识（业务键）
    key: str
    # 前端展示名称
    display_name: str
    # 配置值（初次初始化写入，后续启动不会覆盖用户修改）
    value: str = ""
    # 配置项描述
    description: str = ""


@dataclass
class SettingGroupSeed:
    """种子数据：配置分组，包含其下所有配置项

    字段对应 model/setting_group.py 的列 + items 关联列表。
    """

    # 分组唯一业务键
    key: str
    # 前端展示名称
    display_name: str
    # 分组描述
    description: str = ""
    # 排序序号，用于前端显示排序
    sort_order: int = 0
    # 是否启用
    is_active: bool = True
    # 本组下的配置项
    items: list[SettingItemSeed] = field(default_factory=list)


# —— 系统默认配置数据 ——
# 新增或修改配置项时直接改这里，重启应用会自动同步到数据库
# （不会覆盖已存在的 value，只会补全缺失的项）

SETTING_SEEDS: list[SettingGroupSeed] = [
    SettingGroupSeed(
        key="aliyun_oss",
        display_name="阿里云OSS上传设置",
        description="阿里云OSS对象存储上传配置",
        sort_order=1,
        items=[
            SettingItemSeed(
                key="oss_endpoint",
                value="",
                display_name="OSS Endpoint",
                description="登录名称/显示名称，例如 oss-cn-hangzhou.aliyuncs.com",
            ),
            SettingItemSeed(
                key="oss_access_key_id",
                value="",
                display_name="AccessKey ID",
                description="RAM 用户的 AccessKey ID",
            ),
            SettingItemSeed(
                key="oss_access_key_secret",
                value="",
                display_name="AccessKey Secret",
                description="RAM 用户的 AccessKey Secret",
            ),
            SettingItemSeed(
                key="oss_bucket_name",
                value="",
                display_name="Bucket名称",
                description="OSS Bucket名称",
            ),
            SettingItemSeed(
                key="oss_bucket_domain",
                value="",
                display_name="自定义域名",
                description="可选：自定义域名/CDN域名，留空则使用默认域名",
            ),
        ],
    ),
]
