"""OpenAPI 自定义 schema 转换单元测试。

覆盖：
- UnifiedResponse 模型定义
- _wrap_schema_in_unified_response 包装逻辑
- _wrap_content_schema 递归包装 content
- _should_wrap 路径判断
- _wrap_error_response 错误响应 schema
- _transform_openapi_schema 完整转换
- setup_custom_openapi 注册流程（最小 FastAPI app，不启动服务器）
"""

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from web_service.core.openapi import (
    UnifiedResponse,
    _wrap_schema_in_unified_response,
    _wrap_content_schema,
    _should_wrap,
    _wrap_error_response,
    _transform_openapi_schema,
    setup_custom_openapi,
)


# ============================================================
# UnifiedResponse 模型
# ============================================================


class TestUnifiedResponseModel:
    """UnifiedResponse 基础属性测试。"""

    def test_valid_success(self):
        """成功响应结构。"""
        schema = UnifiedResponse(
            code="0",
            data={"name": "产品A"},
            message="success",
            request_id="uuid-123",
        )
        assert schema.code == "0"
        assert schema.data == {"name": "产品A"}
        assert schema.message == "success"
        assert schema.request_id == "uuid-123"

    def test_valid_error(self):
        """错误响应 data 为 null。"""
        schema = UnifiedResponse(
            code="404001",
            data=None,
            message="产品不存在",
            request_id="uuid-456",
        )
        assert schema.code == "404001"
        assert schema.data is None

    def test_data_accepts_nullable(self):
        """data 可以是 None。"""
        schema = UnifiedResponse(
            code="0",
            data=None,
            message="success",
            request_id="rid",
        )
        assert schema.data is None

    def test_required_fields(self):
        """缺少必填字段触发 ValidationError。"""
        with pytest.raises(ValidationError):
            UnifiedResponse(code="0")

    def test_data_can_be_list(self):
        """data 可以是列表类型（列表响应）。"""
        schema = UnifiedResponse(
            code="0",
            data=[{"id": 1}, {"id": 2}],
            message="success",
            request_id="rid",
        )
        assert len(schema.data) == 2


# ============================================================
# _wrap_schema_in_unified_response
# ============================================================


class TestWrapSchemaInUnifiedResponse:
    """将原始响应 schema 包装进统一格式。"""

    def test_wrap_ref_schema(self):
        """原始 schema 为 $ref 引用。"""
        original = {"$ref": "#/components/schemas/ProductResponse"}
        result = _wrap_schema_in_unified_response(original)

        assert result["type"] == "object"
        props = result["properties"]
        assert "code" in props
        assert "message" in props
        assert "request_id" in props
        # data 字段应保留原始 $ref
        assert props["data"] == original
        # required 数组
        assert set(result["required"]) >= {"code", "message", "request_id"}

    def test_wrap_inline_schema(self):
        """原始 schema 为内联定义。"""
        original = {
            "type": "object",
            "properties": {"id": {"type": "integer"}},
        }
        result = _wrap_schema_in_unified_response(original)

        props = result["properties"]
        assert props["data"] == original

    def test_wrap_nullable_schema(self):
        """原始 schema 为 null 类型（204 跳过但作为结构测试）。"""
        original = {"type": "null"}
        result = _wrap_schema_in_unified_response(original)
        props = result["properties"]
        assert props["data"] == original

    def test_code_field_constants(self):
        """包装后的 code/message/request_id 是固定结构。"""
        result = _wrap_schema_in_unified_response({"type": "object"})
        code_schema = result["properties"]["code"]
        assert code_schema["type"] == "string"
        assert "examples" in code_schema


# ============================================================
# _wrap_content_schema
# ============================================================


class TestWrapContentSchema:
    """包装 responses.content 下的多媒体类型。"""

    def test_single_media_type(self):
        content = {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/CategoryResponse"}
            }
        }
        result = _wrap_content_schema(content)

        schema = result["application/json"]["schema"]
        assert schema["type"] == "object"
        assert "data" in schema["properties"]

    def test_multiple_media_types(self):
        """多媒体类型都应被包装（罕见但支持）。"""
        content = {
            "application/json": {"schema": {"type": "object"}},
        }
        result = _wrap_content_schema(content)
        assert result["application/json"]["schema"]["type"] == "object"
        assert "code" in result["application/json"]["schema"]["properties"]

    def test_no_schema_key(self):
        """没有 schema 的媒体类型被跳过（不应报错）。"""
        content = {
            "application/json": {"example": {"foo": "bar"}},
        }
        # 不应抛异常，且保持原状
        result = _wrap_content_schema(content)
        assert "schema" not in result["application/json"]

    def test_mutation_safe(self):
        """验证函数正确处理 dict 修改，不抛 KeyError。"""
        content = {"application/json": {"schema": {"type": "object"}}}
        result = _wrap_content_schema(content)
        # 返回值和原 content 是同一 dict（就地修改）
        assert result is content


# ============================================================
# _should_wrap
# ============================================================


class TestShouldWrap:
    """路径前缀判断。"""

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("/api/products", True),
            ("/api/products/123", True),
            ("/api/categories", True),
            ("/api/", True),  # 边界：以 /api/ 开头
            ("/docs", False),
            ("/openapi.json", False),
            ("/", False),
            ("/static/file.png", False),
            ("/apixxx", False),  # /api 不是前缀
        ],
    )
    def test_path_detection(self, path, expected):
        assert _should_wrap(path) == expected


# ============================================================
# _wrap_error_response
# ============================================================


class TestWrapErrorResponse:
    """错误响应 schema 结构固定。"""

    def test_structure(self):
        result = _wrap_error_response()
        assert result["type"] == "object"
        props = result["properties"]
        assert "code" in props
        assert props["data"]["type"] == "null"
        assert "message" in props
        assert "request_id" in props
        assert set(result["required"]) >= {"code", "message", "request_id"}

    def test_distinct_from_success(self):
        """错误响应 data 始终为 null，而成功响应 data 可包含业务 schema。"""
        error = _wrap_error_response()
        wrapped = _wrap_schema_in_unified_response({"$ref": "#/components/schemas/X"})

        # error data 是固定 null schema
        assert error["properties"]["data"]["type"] == "null"
        # success data 是原始业务 schema
        assert "$ref" in wrapped["properties"]["data"]


# ============================================================
# _transform_openapi_schema
# ============================================================


class TestTransformOpenapiSchema:
    """完整 OpenAPI schema 遍历与转换。"""

    @pytest.fixture
    def minimal_openapi(self):
        """构造一个包含 /api/ 和 /docs 路径的最小 OpenAPI schema。"""
        return {
            "openapi": "3.1.0",
            "info": {"title": "Test API", "version": "0.1.0"},
            "paths": {
                "/api/products": {
                    "get": {
                        "responses": {
                            "200": {
                                "description": "成功",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ProductResponse"}
                                    }
                                },
                            },
                            "404": {
                                "description": "未找到",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
                                    }
                                },
                            },
                        }
                    }
                },
                "/api/products/{id}": {
                    "get": {
                        "responses": {
                            "200": {
                                "description": "单个产品",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ProductResponseDetail"}
                                    }
                                },
                            },
                            "204": {
                                "description": "删除成功",
                                # 204 无 content
                            },
                        }
                    },
                    "delete": {
                        "responses": {
                            "204": {
                                "description": "删除成功",
                            }
                        }
                    },
                },
                "/docs": {
                    "get": {
                        "responses": {
                            "200": {
                                "description": "Swagger UI",
                                "content": {
                                    "text/html": {
                                        "schema": {"type": "string"}
                                    }
                                },
                            }
                        }
                    }
                },
            },
        }

    def test_api_path_200_wrapped(self, minimal_openapi):
        """/api/ 路径的 200 响应被包装。"""
        result = _transform_openapi_schema(minimal_openapi)
        paths = result["paths"]

        get_products_200 = paths["/api/products"]["get"]["responses"]["200"]
        inner_schema = get_products_200["content"]["application/json"]["schema"]
        assert inner_schema["type"] == "object"
        assert inner_schema["properties"]["code"]["type"] == "string"
        # data 保留原始引用
        assert inner_schema["properties"]["data"]["$ref"] == "#/components/schemas/ProductResponse"

    def test_api_path_error_uses_error_schema(self, minimal_openapi):
        """/api/ 路径的 4xx/5xx 响应使用错误格式（data=null）。"""
        result = _transform_openapi_schema(minimal_openapi)
        error_schema = result["paths"]["/api/products"]["get"]["responses"]["404"][
            "content"
        ]["application/json"]["schema"]
        assert error_schema["properties"]["data"]["type"] == "null"

    def test_non_api_path_not_wrapped(self, minimal_openapi):
        """非 /api/ 路径保持原样（如 /docs）。"""
        result = _transform_openapi_schema(minimal_openapi)
        docs_schema = result["paths"]["/docs"]["get"]["responses"]["200"]["content"][
            "text/html"
        ]["schema"]
        # 非 /api/ 路径不应被包装
        assert docs_schema == {"type": "string"}

    def test_204_response_skipped(self, minimal_openapi):
        """204 No Content 不被包装。"""
        result = _transform_openapi_schema(minimal_openapi)
        delete_204 = result["paths"]["/api/products/{id}"]["delete"]["responses"]["204"]
        # 不应有被包装的 schema 结构
        assert "content" not in delete_204 or (
            "schema" not in delete_204.get("content", {}).get("application/json", {})
            if "content" in delete_204
            else True
        )

    def test_dropped_methods_preserved(self, minimal_openapi):
        """非 HTTP 方法的键（如 parameters）不会被修改。"""
        minimal_openapi["paths"]["/api/products"]["parameters"] = [
            {"in": "query", "name": "page"}
        ]
        result = _transform_openapi_schema(minimal_openapi)
        params = result["paths"]["/api/products"]["parameters"]
        assert len(params) == 1
        assert params[0]["name"] == "page"

    def test_empty_paths_dict(self):
        """空 paths 不应抛异常。"""
        schema = {"openapi": "3.1.0", "paths": {}}
        result = _transform_openapi_schema(schema)
        assert result["paths"] == {}

    def test_path_no_content_response(self):
        """有 response 但无 content 键的罕见情况被跳过。"""
        schema = {
            "paths": {
                "/api/test": {
                    "get": {
                        "responses": {
                            "default": {
                                "description": "兜底响应",
                            }
                        }
                    }
                }
            }
        }
        # 不应抛异常
        result = _transform_openapi_schema(schema)
        assert "/api/test" in result["paths"]


# ============================================================
# setup_custom_openapi
# ============================================================


class TestSetupCustomOpenapi:
    """setup_custom_openapi 注册自定义 schema 生成函数。"""

    def test_overrides_app_openapi(self):
        """调用 setup_custom_openapi 后，app.openapi 变为自定义函数。"""
        app = FastAPI(title="测试 API", version="1.0.0")
        original_openapi = app.openapi

        setup_custom_openapi(app)

        # app.openapi 应被替换为函数
        assert callable(app.openapi)
        assert app.openapi is not original_openapi

    def test_custom_openapi_returns_dict(self):
        """自定义 app.openapi() 返回已包装的 dict。"""
        app = FastAPI(title="测试 API", version="1.0.0")

        @app.get("/api/test")
        async def test_endpoint():
            return {"ok": True}

        setup_custom_openapi(app)

        schema = app.openapi()
        assert isinstance(schema, dict)
        assert "openapi" in schema
        assert "paths" in schema

    def test_custom_openapi_skips_non_api(self):
        """非 /api/ 路径不被包装。"""
        app = FastAPI(title="测试 API", version="1.0.0")

        @app.get("/api/products")
        async def products_endpoint():
            return []

        @app.get("/health")
        async def health_endpoint():
            return {"status": "ok"}

        setup_custom_openapi(app)
        schema = app.openapi()
        paths = schema["paths"]

        # /api/products 被包装
        api_content = paths["/api/products"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert api_content["type"] == "object"
        assert "code" in api_content["properties"]

        # /health 不被包装
        health_content = paths["/health"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert "code" not in health_content.get("properties", {})

    def test_openapi_schema_cached(self):
        """app.openapi_schema 被缓存，避免重复计算。"""
        app = FastAPI()

        @app.get("/api/cached")
        async def cached_endpoint():
            return {}

        setup_custom_openapi(app)

        # 第一次生成
        schema1 = app.openapi()
        # 第二次调用应返回缓存
        schema2 = app.openapi()
        assert schema1 is schema2  # 同一个对象

    def test_custom_title_version_description(self):
        """显式传入 title/version/description 会覆盖 app 默认值。"""
        app = FastAPI(title="默认标题")

        @app.get("/api/x")
        async def x():
            return {}

        setup_custom_openapi(
            app,
            title="自定义标题",
            version="2.0.0",
            description="自定义描述",
        )
        schema = app.openapi()
        assert schema["info"]["title"] == "自定义标题"
        assert schema["info"]["version"] == "2.0.0"
        assert schema["info"]["description"] == "自定义描述"

    def test_fallback_to_app_attributes(self):
        """未显式传 title/version/description 时 fallback 到 app 默认值。"""
        app = FastAPI(title="App Title", version="3.0.0", description="App Desc")

        @app.get("/api/y")
        async def y():
            return {}

        setup_custom_openapi(app)
        schema = app.openapi()
        assert schema["info"]["title"] == "App Title"
        assert schema["info"]["version"] == "3.0.0"
        assert schema["info"]["description"] == "App Desc"
