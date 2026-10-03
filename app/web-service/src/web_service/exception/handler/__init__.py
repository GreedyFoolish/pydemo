"""
FastAPI 异常处理器子包。

三层职责分离：
- mapping.py     查表：异常类型 / HTTP状态码 → ErrorCode
- extractors.py  提取：异常实例 → 可读 message / detail 字符串
- handlers.py    编排：exception_handler 主流程 + JSONResponse 构造

对外导出 exception_handler 及映射表 / 查找函数，
在 main.py 中通过 ``app.add_exception_handler()`` 注册。
"""

from web_service.exception.handler.extractors import extract_detail, extract_message
from web_service.exception.handler.handlers import exception_handler
from web_service.exception.handler.mapping import (
    EXCEPTION_ERROR_CODE_MAP,
    HTTP_STATUS_ERROR_CODE_MAP,
    resolve_error_code,
)

__all__ = [
    "EXCEPTION_ERROR_CODE_MAP",
    "HTTP_STATUS_ERROR_CODE_MAP",
    "exception_handler",
    "extract_detail",
    "extract_message",
    "resolve_error_code",
]
