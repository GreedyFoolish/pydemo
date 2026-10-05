"""异常映射模块单元测试 —— mapping.resolve_error_code。

覆盖三层查找策略：
1. BusinessException → 直接读取自身 error_code
2. HTTPException → 按 status_code 查 HTTP_STATUS_ERROR_CODE_MAP
3. 其他异常 → 按 MRO 遍历 EXCEPTION_ERROR_CODE_MAP
"""

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from web_service.exception import BusinessException, ErrorCode
from web_service.exception.handler.mapping import (
    HTTP_STATUS_ERROR_CODE_MAP,
    EXCEPTION_ERROR_CODE_MAP,
    resolve_error_code,
)


class TestResolveErrorCodeBusinessException:
    """BusinessException 直接返回自身 error_code。"""

    def test_returns_self_error_code(self):
        exc = BusinessException(error_code=ErrorCode.NOT_FOUND)
        result = resolve_error_code(exc)
        assert result == ErrorCode.NOT_FOUND


class TestResolveErrorCodeHTTPException:
    """HTTPException 按 status_code 精细映射。"""

    @pytest.mark.parametrize(
        "status_code, expected",
        [
            (400, ErrorCode.BAD_REQUEST),
            (401, ErrorCode.UNAUTHORIZED),
            (403, ErrorCode.FORBIDDEN),
            (404, ErrorCode.NOT_FOUND),
            (405, ErrorCode.METHOD_NOT_ALLOWED),
            (409, ErrorCode.CONFLICT),
            (422, ErrorCode.VALIDATION_ERROR),
            (429, ErrorCode.RATE_LIMITED),
            (500, ErrorCode.INTERNAL_ERROR),
            (502, ErrorCode.BAD_GATEWAY),
            (503, ErrorCode.SERVICE_UNAVAILABLE),
            (504, ErrorCode.GATEWAY_TIMEOUT),
        ],
    )
    def test_mapped_status_codes(self, status_code, expected):
        exc = HTTPException(status_code=status_code)
        result = resolve_error_code(exc)
        assert result == expected

    def test_unknown_status_falls_back_bad_request(self):
        """未在映射表中的状态码回退 BAD_REQUEST。"""
        exc = HTTPException(status_code=418)  # I'm a teapot
        result = resolve_error_code(exc)
        assert result == ErrorCode.BAD_REQUEST

    def test_all_mapping_entries_have_correct_status(self):
        """映射表完整性：表中所有 status_code 都能映射到对应 ErrorCode。"""
        for status_code, expected in HTTP_STATUS_ERROR_CODE_MAP.items():
            exc = HTTPException(status_code=status_code)
            result = resolve_error_code(exc)
            assert result == expected, (
                f"HTTP status {status_code} should map to {expected}, got {result}"
            )


class TestResolveErrorCodeExceptionMRO:
    """其他异常按 MRO 匹配 EXCEPTION_ERROR_CODE_MAP。"""

    def test_request_validation_error(self):
        """FastAPI RequestValidationError → VALIDATION_ERROR。"""
        exc = RequestValidationError(errors=[], body={})
        result = resolve_error_code(exc)
        assert result == ErrorCode.VALIDATION_ERROR

    def test_integrity_error(self):
        """SQLAlchemy IntegrityError → DB_ERROR。"""
        orig = Exception("FK violation")
        exc = IntegrityError("stmt", "params", orig)
        result = resolve_error_code(exc)
        assert result == ErrorCode.DB_ERROR

    def test_sqlalchemy_error(self):
        """一般 SQLAlchemyError → DB_ERROR。"""
        exc = SQLAlchemyError("DB connection lost")
        result = resolve_error_code(exc)
        assert result == ErrorCode.DB_ERROR

    def test_custom_exception_falls_back_internal(self):
        """未注册的自定义异常 → INTERNAL_ERROR。"""

        class UnknownError(Exception):
            pass

        exc = UnknownError("未知错误")
        result = resolve_error_code(exc)
        assert result == ErrorCode.INTERNAL_ERROR

    def test_standalone_value_error_falls_back_internal(self):
        """标准 ValueError 未在映射表中 → INTERNAL_ERROR。"""
        exc = ValueError("bad value")
        result = resolve_error_code(exc)
        assert result == ErrorCode.INTERNAL_ERROR


class TestMappingTables:
    """验证映射表完整性与设计意图。"""

    def test_http_status_map_covers_common_codes(self):
        """应覆盖常见的 4xx 和 5xx 状态码。"""
        assert 400 in HTTP_STATUS_ERROR_CODE_MAP
        assert 404 in HTTP_STATUS_ERROR_CODE_MAP
        assert 409 in HTTP_STATUS_ERROR_CODE_MAP
        assert 422 in HTTP_STATUS_ERROR_CODE_MAP
        assert 500 in HTTP_STATUS_ERROR_CODE_MAP

    def test_exception_map_specific_before_generic(self):
        """IntegrityError 应在 SQLAlchemyError 之前（更具体 → 更通用）。"""
        keys = list(EXCEPTION_ERROR_CODE_MAP.keys())
        integrity_idx = keys.index(IntegrityError)
        sqlalchemy_idx = keys.index(SQLAlchemyError)
        assert integrity_idx < sqlalchemy_idx

    def test_exception_always_has_exception_key(self):
        """EXCEPTION_ERROR_CODE_MAP 必须包含 Exception 作为最终兜底。"""
        assert Exception in EXCEPTION_ERROR_CODE_MAP
        assert EXCEPTION_ERROR_CODE_MAP[Exception] == ErrorCode.INTERNAL_ERROR
