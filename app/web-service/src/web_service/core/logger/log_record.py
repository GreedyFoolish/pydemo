"""日志记录基类模块

提供日志记录的基础设施：
- LogLevel: 日志级别枚举
- request_id_var: 请求 ID 上下文变量，用于跨异步调用追踪
- setup_logging: 日志系统初始化配置
- LogRecord: 日志记录基类，支持自动计时和多级别输出
"""

import contextvars
import sys
import time
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from loguru import logger
from web_service.core.config import common_settings, log_settings


class LogLevel(StrEnum):
    """日志级别枚举

    定义所有支持的日志级别，用于 LogRecord._emit() 方法。
    """

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# 请求 ID 上下文变量，用于在异步调用链中传递请求标识
# 中间件会在请求开始时设置，日志记录时自动读取
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_request_id", default=""
)


def setup_logging() -> None:
    """初始化日志系统配置。

    根据运行环境设置不同的日志输出方式：
    - production: 输出 JSON 格式到 stdout，便于日志收集系统解析
    - development: 输出彩色格式到 stdout + 错误日志到 tmp/errors.log
    """
    logger.remove()
    if common_settings.environment == "production":
        logger.add(
            sys.stdout,
            level=log_settings.level,
            serialize=True,
        )
    else:
        logger.add(
            sys.stdout,
            level=log_settings.level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{extra[request_id]}</cyan> | "
                "<yellow>{extra[duration_ms]}ms</yellow> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            colorize=True,
        )
        error_log_dir = Path(__file__).resolve().parents[6] / "tmp"
        error_log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(error_log_dir / "errors.log"),
            level="ERROR",
            rotation="10 MB",
            retention="7 days",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{extra[request_id]} | "
                "{extra[duration_ms]}ms | "
                "{name}:{function}:{line} | "
                "{message}\n{exception}"
            ),
        )


@dataclass
class LogRecord:
    """日志记录基类。

    提供日志记录的基础功能：
    - 自动计时：从实例化到调用日志方法的时间差
    - 多级别输出：trace/debug/info/success/warning/error/critical
    - 请求 ID 追踪：自动从上下文变量读取 request_id
    - 扩展字段：子类可添加自定义字段，会自动包含在日志中

    使用方式::

        log = LogRecord(message="操作完成")
        log.info()  # 输出 INFO 级别日志，自动计算 duration_ms

        # 子类扩展示例
        @dataclass
        class MyLog(LogRecord):
            user_id: int = 0

        log = MyLog(message="用户登录", user_id=123)
        log.success()  # 日志中会包含 user_id=123
    """

    # 日志消息
    message: str
    # 操作耗时（毫秒），未显式设置时自动计算
    duration_ms: float = 0.0

    def __post_init__(self) -> None:
        """记录实例化时间，用于自动计算 duration_ms。"""
        self._start_time: float = time.perf_counter()

    def _emit(self, level: LogLevel, exc: Exception | None = None) -> None:
        """输出日志的核心方法。

        参数:
            level: 日志级别
            exc: 可选的异常对象，用于记录异常堆栈
        """
        data = asdict(self)
        message = data.pop("message")

        extra = {k: v for k, v in data.items() if v}
        if not extra.get("duration_ms"):
            extra["duration_ms"] = round(
                (time.perf_counter() - self._start_time) * 1000, 2
            )

        rid = request_id_var.get()
        extra.setdefault("request_id", rid or "-")

        log = logger.bind(**extra) if extra else logger
        if exc:
            log = log.opt(exception=exc)
        getattr(log, level.lower())(message)

    def trace(self) -> None:
        """输出 TRACE 级别日志。"""
        self._emit(LogLevel.TRACE)

    def debug(self) -> None:
        """输出 DEBUG 级别日志。"""
        self._emit(LogLevel.DEBUG)

    def info(self) -> None:
        """输出 INFO 级别日志。"""
        self._emit(LogLevel.INFO)

    def success(self) -> None:
        """输出 SUCCESS 级别日志。"""
        self._emit(LogLevel.SUCCESS)

    def warning(self) -> None:
        """输出 WARNING 级别日志。"""
        self._emit(LogLevel.WARNING)

    def error(self, exc: Exception | None = None) -> None:
        """输出 ERROR 级别日志。

        参数:
            exc: 可选的异常对象，会记录完整的异常堆栈
        """
        self._emit(LogLevel.ERROR, exc=exc)

    def critical(self) -> None:
        """输出 CRITICAL 级别日志。"""
        self._emit(LogLevel.CRITICAL)
