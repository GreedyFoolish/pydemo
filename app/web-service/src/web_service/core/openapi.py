"""
自定义 OpenAPI Schema 生成模块。

解决的问题：FastAPI 的 Swagger UI 默认展示的响应体是路由函数 response_model 声明的原始类型，
而实际运行时统一响应体中间件会将所有 /api/ 路径的响应包装成
{code, data, message, request_id} 结构，导致文档与实际不一致。

本模块通过以下步骤让 Swagger 展示正确的响应格式：
1. 定义与中间件输出一致的 UnifiedResponse 泛型模型
2. 覆盖 app.openapi() 方法，将自动生成的 schema 中每个响应体
   都包装进 UnifiedResponse 结构，同时保留原始 schema 作为 data 字段

使用方式（在 main.py 中）：
    from web_service.core.openapi import setup_custom_openapi
    setup_custom_openapi(app, title, version, description)
"""

from typing import Any
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field


# ── 统一响应体模型 ──────────────────────────────────────────────────
class UnifiedResponse(BaseModel):
    """统一响应体结构（与中间件输出格式保持一致）。

    所有成功和失败响应都会被中间件包装成此结构，
    其中 data 字段承载业务数据或 null。
    """

    code: str = Field(
        description="业务状态码。'0' 表示成功，其他值表示各类业务错误",
        examples=["0", "404001", "400001", "500"],
    )
    data: Any = Field(
        default=None,
        description="业务数据。成功时为路由返回的原始 JSON 对象/数组/值；失败时为 null",
    )
    message: str = Field(
        description="状态描述。成功时为 'success'；失败时为用户友好的错误消息",
        examples=["success", "产品不存在", "参数校验失败"],
    )
    request_id: str = Field(
        description="请求唯一标识（UUID），用于链路追踪和问题排查",
    )


# ── 核心逻辑：包装 OpenAPI schema ──────────────────────────────────
def _wrap_schema_in_unified_response(original_schema: dict) -> dict:
    """将原始响应 schema 包装进 UnifiedResponse 结构。

    原始 schema 会被放到 data 字段中，code/message/request_id 使用固定定义。
    """
    data_schema = original_schema
    # 如果 original_schema 已经是响应引用（{"$ref": "..."}）或内联定义，直接作为 data
    return {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "业务状态码。'0' 表示成功，其他值表示各类业务错误",
                "examples": ["0", "404001", "400001", "500"],
            },
            "data": data_schema,
            "message": {
                "type": "string",
                "description": "状态描述。成功时为 'success'；失败时为用户友好的错误消息",
                "examples": ["success", "产品不存在", "参数校验失败"],
            },
            "request_id": {
                "type": "string",
                "description": "请求唯一标识（UUID），用于链路追踪和问题排查",
            },
        },
        "required": ["code", "message", "request_id"],
    }


def _wrap_content_schema(content: dict) -> dict:
    """包装 responses.content 下的所有媒体类型 schema。

    FastAPI 的 responses 结构：
        "responses": {
            "200": {
                "description": "...",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ProductResponse"}
                    }
                }
            }
        }
    """
    for media_type, media_obj in content.items():
        if "schema" in media_obj:
            media_obj["schema"] = _wrap_schema_in_unified_response(media_obj["schema"])
    return content


def _should_wrap(path: str) -> bool:
    """判断该路径的响应是否应该被包装。

    与中间件保持一致：只包装 /api/ 前缀的路径。
    """
    return path.startswith("/api/")


def _wrap_error_response() -> dict:
    """为错误响应（4xx/5xx）生成与异常处理器一致的 schema。

    错误响应格式与中间件统一格式完全相同，data 始终为 null，
    由异常处理器填充 code/message/request_id。
    """
    return {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "业务错误码（如 '404001'、'422001'）",
                "examples": ["404001", "422001", "500001"],
            },
            "data": {
                "type": "null",
                "description": "错误响应 data 始终为 null",
            },
            "message": {
                "type": "string",
                "description": "用户友好的错误消息",
            },
            "request_id": {
                "type": "string",
                "description": "请求唯一标识（UUID），用于链路追踪和问题排查",
            },
        },
        "required": ["code", "message", "request_id"],
    }


def _transform_openapi_schema(openapi_schema: dict) -> dict:
    """遍历整个 OpenAPI schema，将所有 /api/ 路径的响应体包装成统一格式。"""
    paths = openapi_schema.get("paths", {})

    for path, path_item in paths.items():
        # 非 /api/ 路径跳过（如 /docs、/openapi.json 等）
        if not _should_wrap(path):
            continue

        # path_item 包含 get/post/put/delete/patch/options/head/trace 等方法
        for method_key, method_obj in path_item.items():
            # 跳过非 HTTP 方法的键（如 parameters、servers 等）
            if method_key.lower() not in {
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "options",
                "head",
                "trace",
            }:
                continue

            responses = method_obj.get("responses", {})
            for status_code, response_def in responses.items():
                # 204 No Content 没有响应体，跳过
                if status_code == "204" or status_code == "default":
                    continue

                content = response_def.get("content", {})
                if not content:
                    # 有 response 但无 content（罕见），跳过
                    continue

                # 根据状态码决定包装方式
                status_num = int(status_code) if status_code.isdigit() else 200
                if 200 <= status_num < 300:
                    # 成功响应：包装原始 schema
                    _wrap_content_schema(content)
                else:
                    # 错误响应：使用统一错误格式（data 为 null）
                    for media_type in list(content.keys()):
                        content[media_type]["schema"] = _wrap_error_response()

    return openapi_schema


# ── 对外接口 ───────────────────────────────────────────────────────
def setup_custom_openapi(
    app: FastAPI,
    title: str | None = None,
    version: str | None = None,
    description: str | None = None,
) -> None:
    """为 FastAPI 应用注册自定义 OpenAPI schema 生成函数。

    调用后，访问 /openapi.json 将返回响应体已包装为
    {code, data, message, request_id} 格式的 schema。

    Args:
        app: FastAPI 应用实例
        title: OpenAPI 文档标题（默认使用 app.title）
        version: OpenAPI 文档版本（默认使用 app.version）
        description: OpenAPI 文档描述（默认使用 app.description）
    """

    def custom_openapi() -> dict:
        # 缓存生成结果，避免重复计算
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=title or app.title,
            version=version or app.version or "0.1.0",
            description=description or app.description or "",
            routes=app.routes,
        )

        # 将所有 /api/ 路径的响应体包装成统一格式
        _transform_openapi_schema(openapi_schema)

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    # 覆盖 FastAPI 默认的 openapi() 方法
    app.openapi = custom_openapi  # type: ignore[assignment]
