from pydantic_settings import BaseSettings


class _BaseSettingsWithEnv(BaseSettings):
    # 配置读取方式
    model_config = {
        # env文件位置
        "env_file": ".env"
    }


# 通用配置
class _CommonSettings(_BaseSettingsWithEnv):
    environment: str = "development"


# web服务配置
class _WebSettings(_BaseSettingsWithEnv):
    # 实际读取 WEB_APP_NAME
    app_name: str = "Web Service API"

    # 配置读取方式
    model_config = {"env_prefix": "WEB_"}


# 数据库配置
class _DBSettings(_BaseSettingsWithEnv):
    host: str = ""
    port: str = ""
    name: str = ""
    user: str = ""
    password: str = ""

    model_config = {"env_prefix": "DB_"}


common_settings = _CommonSettings()
web_settings = _WebSettings()
db_settings = _DBSettings()
