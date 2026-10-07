"""
请求响应时间统计中间件。

记录每个请求从进入到离开的完整耗时（包含下游中间件、路由处理、统一响应包装等），
并通过 X-Process-Time 响应头返回耗时（毫秒，保留 2 位小数），
同时使用 logging 输出结构化的访问日志。

注册顺序说明：在 Starlette 中间件洋葱模型中，后注册的中间件位于外层。
因此本中间件必须在 unified_response 之后注册，才能捕获包含响应包装在内的完整耗时。
"""

import time
from fastapi import Request
from loguru import logger


async def process_time(request: Request, call_next):
    # 使用 perf_counter 获取高精度计时（墙钟时间，包含 I/O 等待）
    start_time = time.perf_counter()
    response = None

    try:
        response = await call_next(request)
    finally:
        # 无论正常返回还是抛异常，都记录耗时
        duration_ms = (time.perf_counter() - start_time) * 1000

        # 写入响应头（正常响应有 response 对象可用）
        if response is not None:
            try:
                response.headers["X-Process-Time"] = f"{duration_ms:.2f} ms"
            except Exception:
                # 极少数情况下 headers 可能不可写，忽略
                pass

        # 结构化日志记录
        logger.info(
            "request: method=%s path=%s status=%s duration=%.2fms",
            request.method,
            request.url.path,
            getattr(response, "status_code", "?"),
            duration_ms,
        )

    return response


MIDDLEWARE = (process_time, {})
