from fastapi import FastAPI
from web_service.core.config import common_settings, web_settings

# 根据环境变量决定
# is_production = os.getenv("ENVIRONMENT") == "production"
is_production = common_settings.environment == "production"

app = FastAPI(
    title=web_settings.app_name,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

from web_service.api.welcome import router as welcome_router

app.include_router(welcome_router)
