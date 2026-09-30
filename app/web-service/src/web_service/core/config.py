from pydantic_settings import BaseSettings


class CommonSettings(BaseSettings):
    environment: str = "development"


class WebSettings(BaseSettings):
    # 读取 WEB_APP_NAME
    app_name: str = "Web Service API"

    # 读取配置方式
    model_config = {
        # env文件位置
        "env_file": ".env",
        # 当前类中字段使用的前缀
        "env_prefix": "WEB_",
    }


common_settings = CommonSettings()
web_settings = WebSettings()
