"""
数据库异常子类。

包装数据库层抛出的异常（SQLAlchemy 或其他驱动），
在基类 BusinessException 基础上将 original_error 改为必填，
确保每次抛出都保留底层原始异常用于追溯。
"""

from __future__ import annotations

from web_service.exception.base import BusinessException
from web_service.exception.codes import ErrorCode


class DatabaseException(BusinessException):
    """数据库操作异常子类。

    与 BusinessException 的区别：original_error 为必填关键字参数。
    message 未提供时自动使用 error_code.default_message。

    使用示例::

        try:
            await session.commit()
        except IntegrityError as e:
            raise DatabaseException(
                error_code=ErrorCode.DB_UNIQUE_CONFLICT,
                original_error=e,
                message="产品编码已存在",
            ) from e
    """

    def __init__(
        self,
        error_code: ErrorCode,
        message: str | None = None,
        *,
        detail: str = "",
        original_error: Exception,
    ) -> None:
        """构造数据库异常。

        参数:
            error_code: 业务错误码枚举，携带 http_status 和 default_message 元数据
            message: 用户友好的错误描述，若未提供则使用 error_code.default_message
            detail: 可选上下文信息，供日志记录和调试使用
            original_error: 数据库层原始异常引用（必填，关键字传）
        """
        # 仅需把 original_error 从基类的可选提升为必填，其余参数原样透传
        super().__init__(
            error_code=error_code,
            message=message,
            detail=detail,
            original_error=original_error,
        )
