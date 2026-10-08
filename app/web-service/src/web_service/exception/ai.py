"""
AI 服务异常子类。

包装 AI 服务调用流程中抛出的异常（LLM 接口调用、模型推理等），
在基类 BusinessException 基础上将 original_error 改为必填，
确保每次抛出都保留底层原始异常用于追溯。
"""

from web_service.exception import BusinessException, ErrorCode


class AiException(BusinessException):
    """AI 服务异常子类。

    与 BusinessException 的区别：original_error 为必填关键字参数。
    message 未提供时自动使用 error_code.default_message。

    使用示例::

        try:
            response = await openai_client.chat.completions.create(...)
        except openai.APIError as e:
            raise AiException(
                error_code=ErrorCode.AI_SERVICE_ERROR,
                original_error=e,
                message="AI 模型调用失败",
            ) from e
    """

    def __init__(
        self,
        error_code: ErrorCode | None = ErrorCode.AI_SERVICE_ERROR,
        message: str | None = None,
        *,
        detail: str = "",
        original_error: Exception | None = None,
    ) -> None:
        """构造 AI 服务异常。

        参数:
            error_code: 业务错误码枚举，携带 http_status 和 default_message 元数据
            message: 用户友好的错误描述，若未提供则使用 error_code.default_message
            detail: 可选上下文信息，供日志记录和调试使用
            original_error: AI 服务层原始异常引用（必填，关键字传）
        """
        # 仅需把 original_error 从基类的可选提升为必填，其余参数原样透传
        super().__init__(
            error_code=error_code,
            message=message,
            detail=detail,
            original_error=original_error,
        )
