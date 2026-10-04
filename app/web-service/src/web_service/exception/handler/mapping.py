"""
异常类型到 ErrorCode 的映射表。

类似于 ErrorCode 枚举集中管理业务码，本模块集中管理
"第三方/框架异常 → 业务错误码"的映射关系，使全局异常处理器
无需硬编码 isinstance 判断分支。

两层映射：
1. 异常类级别（EXCEPTION_ERROR_CODE_MAP）
   → 适用于 RequestValidationError、SQLAlchemyError 等异常类型固定对应某个 ErrorCode 的场景
2. HTTP 状态码级别（HTTP_STATUS_ERROR_CODE_MAP）
   → 适用于 HTTPException 这种携带 status_code、需要按状态码精细映射 ErrorCode 的场景

扩展方式：在此字典中追加新映射项即可，无需修改处理器代码。
"""

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from web_service.exception import BusinessException, DatabaseException, ErrorCode

# —— HTTP 状态码 → ErrorCode 映射 ——
# HTTPException 携带 status_code，根据状态码精细映射到对应的业务错误码
# 未命中的状态码回退到 BAD_REQUEST
HTTP_STATUS_ERROR_CODE_MAP: dict[int, ErrorCode] = {
    # 4xx 客户端错误
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    # 5xx 服务端错误
    500: ErrorCode.INTERNAL_ERROR,
    502: ErrorCode.BAD_GATEWAY,
    503: ErrorCode.SERVICE_UNAVAILABLE,
    504: ErrorCode.GATEWAY_TIMEOUT,
}


# —— 第三方异常类 → ErrorCode 映射 ——
# 注意：HTTPException 不在此处，它在 HTTP_STATUS_ERROR_CODE_MAP 中按状态码精细映射
# 顺序按"最具体 → 最通用"排列，isinstance 查找时匹配第一个命中的基类
# 未命中任何项时 resolve_error_code 末尾统一兜底为 ErrorCode.INTERNAL_ERROR
EXCEPTION_ERROR_CODE_MAP: dict[type[BaseException], ErrorCode] = {
    # FastAPI / Starlette
    RequestValidationError: ErrorCode.VALIDATION_ERROR,
    # 自定义数据库异常，已在 Service 层捕获并转为 BusinessException
    DatabaseException: ErrorCode.VALIDATION_ERROR,
    # SQLAlchemy（虽然 Service 层已捕获并转 BusinessException，但作为兜底处理未被捕获的情况）
    IntegrityError: ErrorCode.DB_ERROR,
    SQLAlchemyError: ErrorCode.DB_ERROR,
    Exception: ErrorCode.INTERNAL_ERROR,
}


def resolve_error_code(exc: BaseException) -> ErrorCode:
    """根据异常实例查找对应的 ErrorCode。

    查找策略（按优先级）：
    1. BusinessException → 直接读取自身的 error_code 属性
    2. HTTPException     → 根据 exc.status_code 查 HTTP_STATUS_ERROR_CODE_MAP，
                            未命中回退 BAD_REQUEST
    3. 其他异常          → 按 MRO 遍历 EXCEPTION_ERROR_CODE_MAP 的 KEY，
                            匹配第一个命中的基类

    参数:
        exc: 任意异常实例

    返回:
        匹配到的 ErrorCode 枚举成员
    """
    # 1. BusinessException 自带 error_code，优先使用
    if isinstance(exc, BusinessException):
        return exc.error_code

    # 2. HTTPException：按 status_code 精细映射
    if isinstance(exc, HTTPException):
        return HTTP_STATUS_ERROR_CODE_MAP.get(exc.status_code, ErrorCode.BAD_REQUEST)

    # 3. 按 MRO 查找异常类映射表
    for exc_type in type(exc).__mro__:
        if exc_type in EXCEPTION_ERROR_CODE_MAP:
            return EXCEPTION_ERROR_CODE_MAP[exc_type]

    # 兜底：未知异常统一映射为 500 内部错误
    return ErrorCode.INTERNAL_ERROR
