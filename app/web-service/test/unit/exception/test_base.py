"""BusinessException 基类单元测试。

覆盖构造函数、message fallback 链、__str__ 格式化、original_error 传递。
"""

import pytest
from web_service.exception.base import BusinessException
from web_service.exception.codes import ErrorCode


class TestBusinessExceptionInit:
    """BusinessException 构造与属性校验。"""

    def test_basic_construction(self):
        """最基本的构造：仅 error_code。"""
        exc = BusinessException(error_code=ErrorCode.NOT_FOUND)
        assert exc.error_code == ErrorCode.NOT_FOUND
        # message 应 fallback 到 ErrorCode.default_message
        assert exc.message == ErrorCode.NOT_FOUND.default_message
        assert exc.detail == ""
        assert exc.original_error is None

    def test_explicit_message_override(self):
        """显式传入 message 覆盖枚举默认。"""
        exc = BusinessException(
            error_code=ErrorCode.NOT_FOUND,
            message="产品不存在",
        )
        assert exc.message == "产品不存在"
        # 同时继承 status_code 和 code
        assert exc.error_code.http_status == 404
        assert exc.error_code.code == "404001"

    def test_with_detail(self):
        """携带 detail 上下文信息。"""
        exc = BusinessException(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="参数错误",
            detail="field=name",
        )
        assert exc.detail == "field=name"

    def test_with_original_error(self):
        """携带原始异常引用。"""
        orig = ValueError("原始错误")
        exc = BusinessException(
            error_code=ErrorCode.INTERNAL_ERROR,
            original_error=orig,
        )
        assert exc.original_error is orig
        # message 仍使用枚举默认（未显式覆盖）
        assert exc.message == ErrorCode.INTERNAL_ERROR.default_message

    def test_all_keyword_arguments(self):
        """所有参数关键字传递。"""
        orig = RuntimeError("底层错误")
        exc = BusinessException(
            error_code=ErrorCode.DB_UNIQUE_CONFLICT,
            message="主键冲突",
            detail="table=product",
            original_error=orig,
        )
        assert exc.error_code.code == "500101"
        assert exc.message == "主键冲突"
        assert exc.detail == "table=product"
        assert exc.original_error is orig


class TestBusinessExceptionStr:
    """BusinessException.__str__ 格式化测试。"""

    def test_str_without_original(self):
        """无原始异常时的格式化。"""
        exc = BusinessException(
            error_code=ErrorCode.NOT_FOUND,
            message="找不到资源",
        )
        result = str(exc)
        assert "[404001]" in result
        assert "找不到资源" in result

    def test_str_with_original(self):
        """携带原始异常时追加 cause 信息。"""
        orig = ValueError("值非法")
        exc = BusinessException(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="数据校验失败",
            original_error=orig,
        )
        result = str(exc)
        assert "[422001]" in result
        assert "数据校验失败" in result
        assert "ValueError" in result
        assert "值非法" in result


class TestBusinessExceptionErrorCodeAccess:
    """验证从 ErrorCode 读取 code / http_status。"""

    @pytest.mark.parametrize(
        "error_code, expected_code, expected_status",
        [
            (ErrorCode.BAD_REQUEST, "400001", 400),
            (ErrorCode.UNAUTHORIZED, "401001", 401),
            (ErrorCode.FORBIDDEN, "403001", 403),
            (ErrorCode.NOT_FOUND, "404001", 404),
            (ErrorCode.CONFLICT, "409001", 409),
            (ErrorCode.VALIDATION_ERROR, "422001", 422),
            (ErrorCode.DB_UNIQUE_CONFLICT, "500101", 409),
            (ErrorCode.DB_FK_CONFLICT, "500102", 409),
            (ErrorCode.DB_OPERATIONAL_ERROR, "500201", 503),
            (ErrorCode.INTERNAL_ERROR, "500001", 500),
        ],
    )
    def test_error_code_attributes(self, error_code, expected_code, expected_status):
        """ErrorCode 的 code / http_status 属性正确。"""
        exc = BusinessException(error_code=error_code)
        assert exc.error_code.code == expected_code
        assert exc.error_code.http_status == expected_status


class TestErrorCodeEnum:
    """ErrorCode 枚举基础属性测试。"""

    def test_error_code_str_returns_code(self):
        """ErrorCode.__str__ 返回 code 字符串。"""
        assert str(ErrorCode.NOT_FOUND) == "404001"
        assert str(ErrorCode.VALIDATION_ERROR) == "422001"

    def test_error_code_tuple_attributes(self):
        """三元组拆解正确。"""
        ec = ErrorCode.NOT_FOUND
        assert ec.code == "404001"
        assert ec.http_status == 404
        assert ec.default_message == "资源不存在"
