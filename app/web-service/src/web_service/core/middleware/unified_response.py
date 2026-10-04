"""
统一响应体中间件。

职责：
- 仅负责正常响应的统一包装（/api/ 路径）
- 为每个请求生成 request_id 并挂到 request.state
- 防双重包装：检测异常处理器已包装的响应直接透传

异常处理不在此中间件职责范围内。json.loads 等解析异常
自然传播给 FastAPI 全局异常处理器，由其返回结构化错误响应。
"""

import json
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse


def _is_already_wrapped(data) -> bool:
    """判断响应体是否已经是统一响应格式（防双重包装）。

    正常成功响应有 code/message/data/request_id 四个字段；
    异常处理器返回的错误响应有 code/message/detail/request_id，不含 data。
    两者都至少具备 code + message，因此以这两个字段为判断依据。
    """
    if not isinstance(data, dict):
        return False
    return "code" in data and "message" in data


async def unified_response(request: Request, call_next):
    # 生成 request_id 并挂到 request.state 供下游（异常处理器等）使用
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)

    # 204 No Content：HTTP 规范要求绝对不能有 body，直接透传。但是需要补 X-Request-ID header
    if response.status_code == 204:
        response.headers["X-Request-ID"] = request_id
        return response

    # 非 /api/ 路径直接放行（如 Swagger 文档、健康检查等）
    if not request.url.path.startswith("/api/"):
        return response

    # 流式读取响应体
    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    headers = dict(response.headers)
    headers.pop("content-length", None)
    # 先移除已有的，避免异常处理器已设置时重复
    headers.pop("x-request-id", None)
    headers["X-Request-ID"] = request_id

    # 空响应体（如 204 No Content）设为 None，不尝试解析
    # 非空但解析失败的 JSON（JSONDecodeError）自然上抛给异常处理器
    data = json.loads(body) if body else None

    # 防双重包装：如果响应体已经是统一格式（来自全局异常处理器等），直接透传
    if _is_already_wrapped(data):
        # 补充 request_id 字段（如果原响应没有）
        if isinstance(data, dict) and "request_id" not in data:
            data["request_id"] = request_id
        return JSONResponse(
            content=data,
            status_code=response.status_code,
            headers=headers,
        )

    # 正常包装成功响应
    return JSONResponse(
        content={
            "code": "0",
            "data": data,
            "message": "success",
            "request_id": request_id,
        },
        status_code=response.status_code,
        headers=headers,
    )


MIDDLEWARE = (unified_response, {})
