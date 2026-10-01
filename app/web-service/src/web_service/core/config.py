"""
应用配置模块

基于 pydantic-settings 的 BaseSettings 实现分层配置管理。
所有 Settings 子类共享同一个 .env 文件，通过 env_prefix 字段前缀隔离各自的配置项。

继承机制说明：
    pydantic v2 的 model_config 会沿 MRO 逐 key 合并（dict.update 语义），
    子类只写自己需要覆盖的 key 即可，父类的 env_file / extra 等配置会自动继承。
    详见 pydantic._internal._config.ConfigWrapper.for_model()

extra 配置说明：
    forbid  — 遇到未声明的字段直接抛 ValidationError（默认值）
    ignore  — 静默丢弃未声明的字段（本模块使用此值，因为三个类共享一个 .env）
    allow   — 把未声明的字段也存进模型实例
"""

from pydantic_settings import BaseSettings


class _BaseSettingsWithEnv(BaseSettings):
    """所有 Settings 类的公共基类，定义共享的 model_config。

    - env_file: 指定 .env 文件位置，相对路径以进程 cwd 为基准
    - extra: ignore — 忽略 .env 中不属于本类的字段，避免多个 Settings
      类共享同一个 .env 文件时互相干扰（默认值为 forbid，会直接抛 ValidationError）
    """

    model_config = {
        # .env 文件路径，uv run 时 cwd 为 workspace 根，因此能正确找到 .env
        "env_file": ".env",
        # 忽略 .env 中未在本类声明的字段（默认 forbid 会抛 ValidationError）
        "extra": "ignore",
    }


class _CommonSettings(_BaseSettingsWithEnv):
    """通用环境配置（无 env_prefix，读取不带前缀的 .env 变量）

    .env 对应变量：无（environment 用默认值，或显式写 ENVIRONMENT=xxx）
    """

    # 运行环境：development / production，决定 FastAPI 是否暴露 /docs 等文档路径
    environment: str = "development"


class _WebSettings(_BaseSettingsWithEnv):
    """Web 服务相关配置（读取 WEB_ 前缀的 .env 变量）

    .env 对应变量：
        WEB_APP_NAME → app_name
    """

    app_name: str = "Web Service API"

    # 只写 env_prefix，其余配置（env_file / extra）自动继承自 _BaseSettingsWithEnv
    model_config = {"env_prefix": "WEB_"}


class _DBSettings(_BaseSettingsWithEnv):
    """数据库连接配置（读取 DB_ 前缀的 .env 变量）"""

    host: str = ""  # 数据库主机地址，如 localhost
    port: str = ""  # 数据库端口，如 5432
    name: str = ""  # 数据库名
    user: str = ""  # 连接用户名
    password: str = ""  # 连接密码

    model_config = {"env_prefix": "DB_"}


# 模块级单例
# 首次 import 本模块时，pydantic-settings 自动从 .env 读取值并实例化。
# 后续所有模块通过 `from web_service.core.config import common_settings` 引用同一份实例。
common_settings = _CommonSettings()
web_settings = _WebSettings()
db_settings = _DBSettings()
