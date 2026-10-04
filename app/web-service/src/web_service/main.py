"""
FastAPI 应用入口。

负责：
1. 创建 FastAPI 实例
2. 注册全局异常处理器
3. 注册所有 API 路由
"""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from web_service.core.config import common_settings, web_settings
from web_service.exception.handler import exception_handler

# 根据环境变量决定
# is_production = os.getenv("ENVIRONMENT") == "production"
is_production = common_settings.environment == "production"

app = FastAPI(
    title=web_settings.app_name,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

# —— 全局异常处理器注册 ——
app.add_exception_handler(RequestValidationError, exception_handler)
app.add_exception_handler(HTTPException, exception_handler)
app.add_exception_handler(Exception, exception_handler)

# —— 注册路由 ——
from web_service.api.category import router as category_router
from web_service.api.product import router as product_router
from web_service.api.sku import router as sku_router

app.include_router(category_router)
app.include_router(product_router)
app.include_router(sku_router)
