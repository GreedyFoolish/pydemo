"""
FastAPI 应用入口。

负责：
1. 创建 FastAPI 实例
2. 注册全局异常处理器
3. 注册所有 API 路由
4. 启动时初始化系统配置种子数据（lifespan）
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from web_service.core.config import common_settings, web_settings
from web_service.core.database import get_session_factory
from web_service.core.middleware import register_middleware
from web_service.core.openapi import setup_custom_openapi
from web_service.exception.handler import exception_handler

logger = logging.getLogger(__name__)

# 根据环境变量决定
# is_production = os.getenv("ENVIRONMENT") == "production"
is_production = common_settings.environment == "production"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器。

    启动阶段（yield 之前）：
        1. 初始化数据库连接池（get_session_factory 懒加载）
        2. 自动写入系统配置种子数据（幂等，不覆盖用户已修改的 value）
    """
    # —— 启动：初始化系统配置 ——
    from web_service.service.setting_item import SettingItemService

    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            init_service = SettingItemService(session)
            await init_service.init_settings()
            await session.commit()
            logger.info("系统配置初始化完成")
        except Exception:
            await session.rollback()
            logger.exception("系统配置初始化失败（非致命，服务继续启动）")
            # 初始化失败不阻断应用启动，避免种子数据问题导致整个服务不可用

    yield

    # —— 关闭阶段（yield 之后）：暂无需清理的资源 ——
    logger.info("FastAPI 应用已关闭")


app = FastAPI(
    lifespan=lifespan,
    title=web_settings.app_name,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

# —— 注册中间件 ——
register_middleware(app)

# —— 配置自定义 OpenAPI Schema ——
# 将所有 /api/ 路径的响应体包装为与中间件输出一致的 {code, data, message, request_id} 格式
setup_custom_openapi(app)

# —— 全局异常处理器注册 ——
app.add_exception_handler(RequestValidationError, exception_handler)
app.add_exception_handler(HTTPException, exception_handler)
app.add_exception_handler(Exception, exception_handler)

# —— 注册路由 ——
from web_service.api.category import router as category_router
from web_service.api.product import router as product_router
from web_service.api.sku import router as sku_router
from web_service.api.setting_item import router as setting_item_router
from web_service.api.upload import router as upload_router
from web_service.api.auth import router as auth_router

app.include_router(category_router)
app.include_router(product_router)
app.include_router(sku_router)
app.include_router(setting_item_router)
app.include_router(upload_router)
app.include_router(auth_router)
