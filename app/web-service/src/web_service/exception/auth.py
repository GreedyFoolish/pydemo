"""
认证授权异常子类。

包装认证/鉴权流程中抛出的异常（JWT 校验、权限检查等），
在基类 BusinessException 基础上将 original_error 改为必填，
确保每次抛出都保留底层原始异常用于追溯。
"""

from web_service.exception import BusinessException, ErrorCode


class AuthException(BusinessException):
    """认证授权异常子类。

    与 BusinessException 的区别：original_error 为必填关键字参数。
    message 未提供时自动使用 error_code.default_message。

    使用示例::

        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as e:
            raise AuthException(
                error_code=ErrorCode.UNAUTHORIZED,
                original_error=e,
                message="令牌已过期",
            ) from e
    """

    def __init__(
        self,
        error_code: ErrorCode | None = ErrorCode.AUTH_ERROR,
        message: str | None = None,
        *,
        detail: str = "",
        original_error: Exception | None = None,
    ) -> None:
        """构造认证授权异常。

        参数:
            error_code: 业务错误码枚举，携带 http_status 和 default_message 元数据
            message: 用户友好的错误描述，若未提供则使用 error_code.default_message
            detail: 可选上下文信息，供日志记录和调试使用
            original_error: 认证层原始异常引用（必填，关键字传）
        """
        # 仅需把 original_error 从基类的可选提升为必填，其余参数原样透传
        super().__init__(
            error_code=error_code,
            message=message,
            detail=detail,
            original_error=original_error,
        )
