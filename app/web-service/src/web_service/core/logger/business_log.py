"""业务操作日志模块

记录业务层面的操作日志，包括：
- 操作名称（action）
- 操作对象类型（entity）
- 操作对象 ID（entity_id）
- 操作结果（成功/失败）

提供 service_logger 装饰器，用于自动记录 Service 层方法的执行日志。

使用方式::

    # 直接使用
    log = BusinessLog(
        message="创建用户成功",
        action="创建用户",
        entity="User",
        entity_id=123
    )
    log.success()

    # 使用装饰器
    @service_logger(action="创建用户", entity="User")
    async def create_user(self, data: UserCreate) -> User:
        ...
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any
from web_service.exception.base import BusinessException
from web_service.core.logger.log_record import LogRecord


@dataclass
class BusinessLog(LogRecord):
    """业务操作日志记录。

    继承 LogRecord 的自动计时功能，额外记录业务操作相关的字段。
    """

    # 操作名称，如"创建用户"、"删除订单"
    action: str = ""
    # 操作对象类型，如"User"、"Order"
    entity: str = ""
    # 操作对象 ID，可以是字符串或整数
    entity_id: str | int = ""


# ID 提取器函数类型：接收 (args, kwargs, result)，返回 entity_id
EntityIdExtractor = Callable[[tuple, dict[str, Any], Any], str | int]


def service_logger(
    action: str,
    entity: str = "",
    id_extractor: EntityIdExtractor | None = None,
):
    """Service 层方法日志装饰器。

    自动记录方法执行的成功/失败日志，包括：
    - 方法执行耗时
    - 操作名称和对象类型
    - 通过 id_extractor 提取的操作对象 ID
    - 异常信息（如果是 BusinessException 记录为 WARNING，否则记录为 ERROR）

    参数:
        action: 操作名称，如"创建用户"
        entity: 操作对象类型，如"User"
        id_extractor: 可选的 ID 提取函数，签名 (args, kwargs, result) -> entity_id
                     用于从方法参数或返回值中提取操作对象 ID

    使用示例::

        @service_logger(
            action="创建用户",
            entity="User",
            id_extractor=lambda args, kwargs, result: result.id if result else ""
        )
        async def create_user(self, data: UserCreate) -> User:
            ...
    """

    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            log = BusinessLog(
                message="",
                action=action,
                entity=entity,
            )
            try:
                result = await func(*args, **kwargs)
                if id_extractor:
                    try:
                        log.entity_id = id_extractor(args, kwargs, result)
                    except Exception:
                        pass
                log.message = f"{action}成功"
                log.success()
                return result
            except Exception as e:
                if id_extractor:
                    try:
                        log.entity_id = id_extractor(args, kwargs, None)
                    except Exception:
                        pass
                log.message = f"{action}失败"
                if isinstance(e, BusinessException):
                    log.warning()
                else:
                    log.error(exc=e)
                raise

        return wrapper

    return decorator
