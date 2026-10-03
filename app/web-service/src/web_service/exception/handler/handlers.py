"""
FastAPI 全局异常处理器。

将 Python 异常（项目自定义 BusinessException 及第三方框架异常）
统一转换为结构化 JSON 响应，保证 API 错误输出格式一致。

编排职责：
1. BusinessException → 直接使用自身的 error_code / message / detail
2. 第三方异常 → 通过 mapping.resolve_error_code() 查 ErrorCode，extractors.extract_message / extract_detail 提取可读信息

本模块只做流程编排，不含查表逻辑和字符串提取逻辑。前者在 mapping.py，后者在 extractors.py。
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from web_service.exception.base import BusinessException
from web_service.exception.codes import ErrorCode
from web_service.exception.handler.extractors import extract_detail, extract_message
from web_service.exception.handler.mapping import resolve_error_code


async def exception_handler(request: Request, exc: BaseException) -> JSONResponse:
    """统一异常处理器。

    对所有已注册的异常类型（BusinessException / HTTPException /
    RequestValidationError / Exception）返回统一格式的 JSON 响应：
    {
        "code":    业务错误码（如 "404001"）,
        "message": 用户友好消息,
        "detail":  可选的调试上下文,
    }

    HTTP 状态码取自 ErrorCode.http_status。
    """
    # 1. BusinessException 优先使用自身携带的完整信息
    if isinstance(exc, BusinessException):
        return JSONResponse(
            status_code=exc.error_code.http_status,
            content={
                "code": exc.error_code.code,
                "message": exc.message,
                "detail": exc.detail,
            },
        )

    # 2. 第三方异常：查映射表 + 提取可读信息
    error_code: ErrorCode = resolve_error_code(exc)
    return JSONResponse(
        status_code=error_code.http_status,
        content={
            "code": error_code.code,
            "message": extract_message(exc, error_code),
            "detail": extract_detail(exc),
        },
    )
