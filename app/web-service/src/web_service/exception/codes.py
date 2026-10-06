"""
错误码枚举。

每个成员是 (业务码, HTTP状态码, 默认消息) 的三元组，
集中管理错误码的所有元信息，全局异常处理器直接通过
error_code.http_status / error_code.default_message 取值，
无需维护额外的映射表。

设计说明：
- 业务码 code 是前端识别错误的标识（如 "422001"）
- HTTP 状态码在枚举里声明，但异常类本身不感知 Web 层，
  由全局异常处理器读取 error_code.http_status 设置响应码
- 默认消息用于 DatabaseException 等自动推断场景，
  调用方仍可在构造异常时显式传入更具体的 message 覆盖
"""

from enum import Enum


class ErrorCode(Enum):
    """业务错误码枚举。

    成员值格式：(业务码 str, HTTP状态码 int, 默认消息 str)

    通过自定义 __new__ 拆解三元组，使每个成员拥有三个独立属性：
    - .code:          业务码（如 "422001"）
    - .http_status:   HTTP 状态码（如 422）
    - .default_message: 默认用户消息

    覆写 __str__ 返回业务码字符串，使 f-string 中直接写
    ``f"[{ErrorCode.NOT_FOUND}]"`` 即可得到 ``[404001]``。

    扩展方式：在此枚举中添加新成员即可，无需修改已有异常类代码。
    """

    def __new__(cls, code: str, http_status: int, default_message: str):
        """拆解三元组，将各分量绑定到独立属性。"""
        obj = object.__new__(cls)
        obj.code = code
        obj.http_status = http_status
        obj.default_message = default_message
        return obj

    def __str__(self) -> str:
        """返回业务码字符串，方便 f-string 直接使用。"""
        return self.code

    # —— 通用 4xx 客户端错误 ——
    BAD_REQUEST = ("400001", 400, "请求参数不合法")
    UNAUTHORIZED = ("401001", 401, "未认证或认证已过期")
    FORBIDDEN = ("403001", 403, "无权限访问")
    NOT_FOUND = ("404001", 404, "资源不存在")
    METHOD_NOT_ALLOWED = ("405001", 405, "请求方法不允许")
    CONFLICT = ("409001", 409, "资源冲突")
    VALIDATION_ERROR = ("422001", 422, "数据校验错误")
    VALIDATION_FILE_ERROR = ("422002", 422, "文件数据验证错误")
    RATE_LIMITED = ("429001", 429, "请求过于频繁")

    # —— 通用 5xx 服务端错误 ——
    INTERNAL_ERROR = ("500001", 500, "服务器内部错误")
    BAD_GATEWAY = ("502001", 502, "网关错误")
    SERVICE_UNAVAILABLE = ("503001", 503, "服务暂不可用")
    GATEWAY_TIMEOUT = ("504001", 504, "网关超时")

    # —— 数据库错误 ——
    DB_UNIQUE_CONFLICT = ("500101", 409, "数据唯一约束冲突")
    DB_FK_CONFLICT = ("500102", 409, "数据外键约束冲突")
    DB_OPERATIONAL_ERROR = ("500201", 503, "数据库连接异常")
    DB_ERROR = ("500999", 500, "数据库内部错误")

    # —— 预留扩展 ——
    AUTH_ERROR = ("401002", 401, "认证失败")
