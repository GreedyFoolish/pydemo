"""全局异常处理器单元测试 —— exception_handler。

直接调用 exception_handler(request, exc)，用 MagicMock 构造最小请求上下文。
验证：BusinessException / HTTPException / RequestValidationError
都能返回统一响应格式 {code, data, message, request_id}。
"""

import pytest
from unittest.mock import MagicMock
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request

from web_service.exception import BusinessException, ErrorCode
from web_service.exception.handler.handlers import exception_handler

# ============================================================
# 辅助函数
# ============================================================


def _make_request_with_state(request_id: str = "req-uuid-12345") -> Request:
    """构造携带 request.state.request_id 的最小 Request 对象。"""
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.request_id = request_id
    return req


def _body_text(response) -> str:
    """将 response.body 解码为 str，便于中文字符匹配。"""
    return response.body.decode("utf-8")


# ============================================================
# BusinessException 处理
# ============================================================


class TestExceptionHandlerBusinessException:
    """BusinessException 应使用自身携带的完整信息。"""

    @pytest.mark.smoke
    async def test_not_found_response(self):
        exc = BusinessException(error_code=ErrorCode.NOT_FOUND, message="产品不存在")
        req = _make_request_with_state("req-001")

        response = await exception_handler(req, exc)

        assert response.status_code == 404
        assert response.headers["X-Request-ID"] == "req-001"
        text = _body_text(response)
        assert "404001" in text
        assert "null" in text  # data
        assert "产品不存在" in text
        assert "req-001" in text

    async def test_conflict_with_explicit_message(self):
        exc = BusinessException(
            error_code=ErrorCode.DB_UNIQUE_CONFLICT,
            message="SKU 编码已存在",
        )
        req = _make_request_with_state("req-002")

        response = await exception_handler(req, exc)

        assert response.status_code == 409
        text = _body_text(response)
        assert "500101" in text
        assert "SKU 编码已存在" in text

    async def test_internal_error_with_original(self):
        """携带 original_error 不影响响应，只用于日志。"""
        orig = RuntimeError("DB connection dropped")
        exc = BusinessException(
            error_code=ErrorCode.DB_OPERATIONAL_ERROR,
            original_error=orig,
        )
        req = _make_request_with_state("req-003")

        response = await exception_handler(req, exc)

        assert response.status_code == 503
        text = _body_text(response)
        # 使用 fallback 的 default_message
        assert "数据库连接异常" in text


# ============================================================
# HTTPException 处理
# ============================================================


class TestExceptionHandlerHTTPException:
    """HTTPException 经 mapping 查找 ErrorCode，再用 extract_message 取消息。"""

    async def test_http_not_found(self):
        exc = HTTPException(status_code=404, detail="指定资源不存在")
        req = _make_request_with_state("req-010")

        response = await exception_handler(req, exc)

        assert response.status_code == 404
        text = _body_text(response)
        assert "404001" in text
        assert "指定资源不存在" in text

    async def test_http_validation_error(self):
        """422 被映射到 VALIDATION_ERROR。"""
        exc = HTTPException(status_code=422, detail={"field": "name"})
        req = _make_request_with_state("req-011")

        response = await exception_handler(req, exc)

        assert response.status_code == 422
        text = _body_text(response)
        assert "422001" in text

    async def test_http_detail_str(self):
        """HTTPException detail 为 str 时直接使用。"""
        exc = HTTPException(status_code=400, detail="bad request")
        req = _make_request_with_state("req-015")
        response = await exception_handler(req, exc)
        assert response.status_code == 400
        text = _body_text(response)
        assert "bad request" in text


# ============================================================
# RequestValidationError 处理
# ============================================================


class TestExceptionHandlerRequestValidationError:
    """FastAPI 参数校验错误 → VALIDATION_ERROR + 拼接字段消息。"""

    async def test_validation_error(self):
        exc = RequestValidationError(
            errors=[
                {
                    "loc": ("body", "name"),
                    "msg": "field required",
                    "type": "value_error.missing",
                },
            ],
            body={},
        )
        req = _make_request_with_state("req-020")

        response = await exception_handler(req, exc)

        assert response.status_code == 422
        text = _body_text(response)
        assert "422001" in text
        # extract_message 应拼接 loc:msg
        assert "body.name: field required" in text

    async def test_multiple_validation_errors_joined(self):
        exc = RequestValidationError(
            errors=[
                {"loc": ("body", "name"), "msg": "too short", "type": "value_error"},
                {
                    "loc": ("body", "price"),
                    "msg": "must be positive",
                    "type": "value_error",
                },
            ],
            body={},
        )
        req = _make_request_with_state("req-021")

        response = await exception_handler(req, exc)

        assert response.status_code == 422
        text = _body_text(response)
        assert "body.name: too short" in text
        assert "body.price: must be positive" in text


# ============================================================
# 通用异常处理
# ============================================================


class TestExceptionHandlerGenericException:
    """未知异常 → INTERNAL_ERROR + str(exc)。"""

    async def test_value_error(self):
        exc = ValueError("price must be positive")
        req = _make_request_with_state("req-030")

        response = await exception_handler(req, exc)

        assert response.status_code == 500
        text = _body_text(response)
        assert "500001" in text
        assert "price must be positive" in text


# ============================================================
# request.state 缺失 request_id 时的兜底
# ============================================================


class TestExceptionHandlerNoRequestId:
    """request.state 上无 request_id 属性时兜底为空字符串。"""

    async def test_fallback_to_empty(self):
        """request.state 上无 request_id 属性时兜底为空字符串。"""

        class _StateWithoutRequestId:
            """模拟缺少 request_id 属性的 state 对象。"""

        req = MagicMock()
        req.state = _StateWithoutRequestId()

        exc = BusinessException(error_code=ErrorCode.INTERNAL_ERROR)
        response = await exception_handler(req, exc)
        # 不抛异常且返回正确响应
        assert response is not None
        assert response.status_code == 500
