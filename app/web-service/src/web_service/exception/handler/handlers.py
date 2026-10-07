"""
FastAPI 全局异常处理器。

将 Python 异常（项目自定义 BusinessException 及第三方框架异常）
统一转换为与中间件一致的响应格式 {code, data, message, request_id}。

编排职责：
1. BusinessException → 直接使用自身携带的完整信息
2. 第三方异常 → 通过 mapping.resolve_error_code() 查 ErrorCode，extractors.extract_message 提取可读信息

本模块只做流程编排，不含查表逻辑和字符串提取逻辑。前者在 mapping.py，后者在 extractors.py。
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from web_service.exception import BusinessException, ErrorCode
from web_service.exception.handler.extractors import extract_message
from web_service.exception.handler.mapping import resolve_error_code


async def exception_handler(request: Request, exc: BaseException) -> JSONResponse:
    """统一异常处理器。

    对所有已注册的异常类型（BusinessException / HTTPException /
    RequestValidationError / Exception）返回与中间件一致的响应格式：
    {
        "code":       业务错误码（如 "404001"）,
        "data":       始终为 null,
        "message":    用户友好消息,
        "request_id": 请求追踪 ID（来自 middleware 注入的 request.state.request_id）
    }

    HTTP 状态码取自 ErrorCode.http_status。
    """
    # 从 request.state 取 middleware 注入的 request_id（兜底为空字符串）
    request_id = getattr(request.state, "request_id", "")
    # 标记进行错误处理
    request.state.exception_handled = True

    # 1. BusinessException 优先使用自身携带的完整信息
    if isinstance(exc, BusinessException):
        # 请求日志记录
        log = getattr(request.state, "request_log", None)
        if log:
            log.message = f"业务异常: {exc.message}"
            log.warning()
        return JSONResponse(
            status_code=exc.error_code.http_status,
            headers={"X-Request-ID": request_id},
            content={
                "code": exc.error_code.code,
                "data": None,
                "message": exc.message,
                "request_id": request_id,
            },
        )

    # 2. 第三方异常：查映射表 + 提取可读信息
    error_code: ErrorCode = resolve_error_code(exc)
    http_status = error_code.http_status
    message = extract_message(exc, error_code)
    # 请求日志记录
    log = getattr(request.state, "request_log", None)
    if log:
        log.message = f"请求异常: {message}"
        if http_status == 500:
            log.error(exc=exc)
        else:
            log.warning()
    return JSONResponse(
        status_code=error_code.http_status,
        headers={"X-Request-ID": request_id},
        content={
            "code": error_code.code,
            "data": None,
            "message": message,
            "request_id": request_id,
        },
    )
