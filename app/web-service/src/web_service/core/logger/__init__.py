"""日志模块

提供统一的日志记录能力，包括：
- LogRecord: 日志记录基类，支持自动计时和多级别输出
- RequestLog: HTTP 请求日志
- BusinessLog: 业务操作日志
- DBLog: 数据库查询日志
- service_logger: Service 层日志装饰器
"""

from web_service.core.logger.log_record import LogRecord
from web_service.core.logger.request_log import RequestLog
from web_service.core.logger.business_log import BusinessLog, service_logger
from web_service.core.logger.db_log import DBLog

__all__ = ["LogRecord", "RequestLog", "BusinessLog", "service_logger", "DBLog"]
