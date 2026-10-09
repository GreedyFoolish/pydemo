"""
中间件注册模块

提供统一的中间件管理机制，支持函数式和类式中间件的自动注册。
使用方式：
    from app.web_service.core.middleware import register_middleware
    register_middleware(app)

注册顺序说明：Starlette 中间件使用洋葱模型，列表中越靠后的中间件位于外层
（最先收到请求、最后处理响应）。当前顺序：
    1. unified_response  —— 最内层，负责统一响应体包装
    2. process_time      —— 中间层，负责统计包含响应包装在内的完整请求耗时
    3. cors              —— 最外层，负责跨域处理（预检请求在此被快速拦截返回）
"""

import inspect
from fastapi import FastAPI
from typing import Any
from web_service.core.middleware import unified_response, process_time, cors, logging

# 中间件配置列表
# 每个中间件项是一个元组：(callable_obj, kwargs)
# callable_obj: 中间件函数或类
# kwargs: 中间件配置参数
MIDDLEWARES: list[tuple[Any, dict[str, Any]]] = [
    logging.MIDDLEWARE,
    unified_response.MIDDLEWARE,
    process_time.MIDDLEWARE,
    cors.MIDDLEWARE,
]


def register_middleware(app: FastAPI) -> None:
    """
    注册所有中间件到 FastAPI 应用

    Args:
        app: FastAPI 应用实例

    自动识别中间件类型：
    - 如果是类：使用 app.add_middleware()
    - 如果是函数：使用 app.middleware("http")()
    """
    for callable_obj, kwargs in MIDDLEWARES:
        if inspect.isclass(callable_obj):
            # 类式中间件
            app.add_middleware(callable_obj, **kwargs)
        else:
            # 函数式中间件
            app.middleware("http")(callable_obj, **kwargs)
