"""
异常信息提取器。

职责：从第三方异常实例中提取人类可读的 message 和 detail 文本，
与 mapping.py 的"异常→ErrorCode 查表"逻辑解耦。

每个 extractor 函数接收 (异常实例, 兜底 ErrorCode) → 返回 str。
"""

import json
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from web_service.exception.codes import ErrorCode


def extract_message(exc: BaseException, fallback_code: ErrorCode) -> str:
    """从异常中提取可读的用户友好消息。

    参数:
        exc:            任意异常实例
        fallback_code:  已解析的 ErrorCode，当 exc 自身无有效 detail 时
                        使用其 default_message 作为兜底

    返回:
        提取到的消息字符串
    """
    if isinstance(exc, HTTPException):
        # HTTPException.detail 可能是 str、dict、list 或 None
        if isinstance(exc.detail, str) and exc.detail:
            return exc.detail
        if exc.detail is not None:
            # dict / list 等结构化 detail → 转 JSON 字符串保留信息
            try:
                return json.dumps(exc.detail, ensure_ascii=False)
            except TypeError, ValueError:
                return str(exc.detail)
        # detail 为 None → 用 ErrorCode 的默认消息
        return fallback_code.default_message

    if isinstance(exc, RequestValidationError):
        # FastAPI 校验错误：拼接所有字段错误信息
        errors = exc.errors()
        if errors:
            parts = []
            for err in errors:
                loc = ".".join(str(p) for p in err.get("loc", ()))
                msg = err.get("msg", "")
                parts.append(f"{loc}: {msg}" if loc else msg)
            return "; ".join(parts)
        return fallback_code.default_message

    # 其他异常：取 str(exc)，为空则用 ErrorCode 默认消息
    return str(exc) or fallback_code.default_message


def extract_detail(exc: BaseException) -> str:
    """从第三方异常中提取调试详情。

    参数:
        exc: 任意异常实例

    返回:
        调试上下文字符串，无有效信息时返回空串
    """
    if isinstance(exc, HTTPException):
        extra = f"status_code={exc.status_code}"
        if exc.headers:
            extra += f", headers={exc.headers}"
        return extra
    return ""
