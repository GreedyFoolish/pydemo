"""HTTP 请求日志模块

记录每个 HTTP 请求的基本信息，包括：
- 请求方法（GET/POST/PUT/DELETE 等）
- 请求路径
- 响应状态码
- 客户端 IP
- 请求耗时（继承自 LogRecord）

使用方式::

    log = RequestLog(
        message="请求处理完成",
        method="GET",
        path="/api/users",
        status_code=200,
        client_ip="127.0.0.1"
    )
    log.info()
"""

from dataclasses import dataclass
from web_service.core.logger.log_record import LogRecord


@dataclass
class RequestLog(LogRecord):
    """HTTP 请求日志记录。

    继承 LogRecord 的自动计时功能，额外记录请求相关的字段。
    通常由中间件在请求处理完成后创建并输出。
    """

    # HTTP 请求方法：GET / POST / PUT / DELETE / PATCH 等
    method: str = ""
    # 请求路径，如 /api/users/123
    path: str = ""
    # HTTP 响应状态码，如 200 / 404 / 500
    status_code: int = 0
    # 客户端 IP 地址
    client_ip: str = ""
