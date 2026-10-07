"""数据库查询日志模块

记录数据库查询的详细信息，包括：
- SQL 语句
- 查询参数
- 查询耗时（继承自 LogRecord）

用于慢查询监控和数据库性能分析。

使用方式::

    log = DBLog(
        message="查询执行完成",
        sql="SELECT * FROM users WHERE id = %s",
        params="123"
    )
    log.info()

    # 慢查询记录为 WARNING
    if duration > log_settings.slow_query_threshold:
        log.warning()
"""

from dataclasses import dataclass
from web_service.core.logger.log_record import LogRecord


@dataclass
class DBLog(LogRecord):
    """数据库查询日志记录。

    继承 LogRecord 的自动计时功能，额外记录 SQL 查询相关的字段。
    通常由数据库中间件或查询拦截器创建并输出。
    """

    # SQL 查询语句，如 "SELECT * FROM users WHERE id = %s"
    sql: str = ""
    # 查询参数，序列化为字符串格式，如 "123" 或 "(123, 'active')"
    params: str = ""
