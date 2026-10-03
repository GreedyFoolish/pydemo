"""
业务异常基类。

所有业务逻辑层主动抛出的"可预期"异常都应继承 BusinessException。
异常类承载业务语义（错误码 + 消息 + 上下文 + 可选原始异常）。
ErrorCode 富枚举已经集中管理了业务码、HTTP 状态码和默认消息，
全局异常处理器直接读取 error_code.http_status 设置响应码、
读取 error_code.code 作为前端错误标识。

子类扩展方式：在 exception/ 下新建模块（如 database.py、auth.py），
继承 BusinessException 并在子类中补充特定字段和自动推断逻辑。
"""

from __future__ import annotations
from typing import Any
from web_service.exception.codes import ErrorCode


class BusinessException(Exception):
    """业务异常基类。

    所有业务逻辑层主动抛出的"可预期"异常都应继承此类。
    只承载业务语义：错误码 + 用户友好消息 + 可选上下文 + 可选原始异常引用。

    message fallback 链：显式传入 > ErrorCode.default_message
    （DatabaseException 还会再 fallback 到原始异常字符串）。

    构造约束：details 和 original_error 必须用关键字传参，
    避免位置参数顺序歧义、提高调用可读性。

    使用示例::

        # 使用枚举默认消息
        raise BusinessException(error_code=ErrorCode.NOT_FOUND)

        # 覆盖为更具体的消息
        raise BusinessException(
            error_code=ErrorCode.NOT_FOUND,
            message="产品不存在",
            details={"product_id": 123},
        )

        # 包装底层异常
        raise BusinessException(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="数据校验失败",
            original_error=some_validation_error,
        )

    子类扩展示例（见 exception/database.py）::

        class DatabaseException(BusinessException):
            ...
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str | None = None,
        *,
        detail: str = "",
        original_error: Exception | None = None,
    ) -> None:
        """构造业务异常。

        参数:
            error_code: 业务错误码枚举，前端用于精确识别错误类型；
                        同时携带 http_status 和 default_message 元数据
            message: 用户友好的错误描述，若未提供则使用 error_code.default_message
            detail: 可选上下文信息，供日志记录和调试使用；
            original_error: 底层原始异常引用（如数据库驱动、校验库抛出的异常），
                            用于链式追溯和日志定位；纯业务场景不传
        """
        # message fallback：显式传入 > 枚举默认消息
        final_message = message or error_code.default_message

        super().__init__(final_message)
        self.error_code = error_code
        self.message = final_message
        self.detail = detail
        self.original_error = original_error

    def __str__(self) -> str:
        """异常的字符串表示，用于日志记录。

        若持有 original_error 则附带原始异常类型和信息，便于快速定位。
        """
        base = f"[{self.error_code}] {self.message}"
        if self.original_error is not None:
            return f"{base} | caused by: {type(self.original_error).__name__}: {self.original_error}"
        return base
