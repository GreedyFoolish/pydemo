"""
数据库模块。

提供异步引擎和 Session 工厂的懒加载单例管理。
- get_engine(): 返回全局唯一的 AsyncEngine 实例
- get_session_factory(): 返回全局唯一的 async_sessionmaker 实例
- run_in_session(fn): 自动管理 session 创建/关闭，适用于非 FastAPI 依赖注入场景
"""

import time
import weakref
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TypeVar
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from web_service.core.config import db_settings, log_settings

# 全局单例引擎，首次调用 get_engine() 时初始化
_engine: AsyncEngine | None = None
# 记录每条 SQL 执行的起始时间，key 为 ExecutionContext 对象
# 使用 WeakKeyDictionary：context 被 GC 时 entry 自动移除，避免异常中断导致内存泄漏
_query_start_times: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _register_db_events(engine: AsyncEngine) -> None:
    """注册 SQLAlchemy 事件钩子，实现 SQL 执行日志。

    通过 before/after_cursor_execute 拦截每条 SQL，计算耗时后：
    - 慢查询（>= slow_query_threshold）→ WARNING
    - 普通查询 → DEBUG

    延迟导入 DBLog 以避免循环依赖。
    """
    from web_service.core.logger.db_log import DBLog

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        # 以 context 对象为 key 记录起始时间，确保同一执行上下文配对
        _query_start_times[context] = time.perf_counter()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        start = _query_start_times.pop(context, None)
        if start is None:
            return
        duration = (time.perf_counter() - start) * 1000
        # 数据库日志记录
        if duration >= log_settings.slow_query_threshold:
            DBLog(
                message="慢查询",
                sql=statement,
                params=str(parameters),
                duration_ms=round(duration, 2),
            ).warning()
        else:
            DBLog(
                message="SQL执行",
                sql=statement,
                params=str(parameters),
                duration_ms=round(duration, 2),
            ).debug()


def get_engine() -> AsyncEngine:
    """获取数据库异步引擎（懒加载单例）。

    首次调用时根据 db_settings 中的配置创建引擎，
    后续调用直接返回已创建的实例。

    返回:
        AsyncEngine: SQLAlchemy 异步数据库引擎
    """
    global _engine

    if _engine is None:
        # 拼接 PostgreSQL 异步连接 URL
        url = f"postgresql+asyncpg://{db_settings.user}:{db_settings.password}@{db_settings.host}:{db_settings.port}/{db_settings.name}"
        _engine = create_async_engine(
            url,
            pool_size=10,  # 连接池基础大小
            max_overflow=20,  # 连接池最大溢出数
            pool_pre_ping=True,  # 连接前预检测，防止空闲连接断开
            echo=False,  # 关闭 SQLAlchemy 内置日志，改由事件钩子自定义输出
        )
        # 注册 SQL 拦截事件，替代 echo=True 的日志功能
        _register_db_events(_engine)

    return _engine


# 全局单例 Session 工厂，首次调用 get_session_factory() 时初始化
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取异步 Session 工厂（懒加载单例）。

    基于 get_engine() 返回的引擎创建 async_sessionmaker，
    配置 expire_on_commit=False 避免提交后对象过期。
    """
    global _session_factory

    if _session_factory is None:
        _session_factory = async_sessionmaker(
            # 使用 get_engine() 获取数据库引擎
            get_engine(),
            # 指定使用异步 Session 类
            class_=AsyncSession,
            # 设置为 False，避免在提交后过期对象
            expire_on_commit=False,
        )

    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入函数：提供异步数据库会话。

    每次请求创建一个新的 AsyncSession，请求结束后自动提交或回滚事务。
    Service 层不自行管理 session 生命周期，统一由本函数在 yield 之后
    根据异常状态决定 commit / rollback，最后关闭 session。

    使用方式（API 路由中）::

        @router.get("/categories")
        async def list_categories(
            db: AsyncSession = Depends(get_session),
        ) -> list[CategoryResponse]:
            service = CategoryService(db)
            ...

    Yields:
        AsyncSession: 异步数据库会话，在整个请求生命周期内有效
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            # 请求处理成功 → 提交事务
            await session.commit()
        except Exception:
            # 任何异常（包括业务异常）→ 回滚事务，然后向上抛出
            await session.rollback()
            raise


# 泛型类型变量：让 run_in_session 的返回类型自动匹配回调 fn 的返回类型
# 例如 fn 返回 InitReadResult，则 run_in_session 也被推导为 InitReadResult
_T = TypeVar("_T")


async def run_in_session(
    fn: Callable[[AsyncSession], Awaitable[_T]],
) -> _T:
    """在非依赖注入场景下执行需要数据库会话的操作。

    适用场景：WebSocket、后台任务、定时任务等无法使用 FastAPI Depends 的地方。
    与 get_session() 的区别：
    - get_session() 是 FastAPI 依赖注入函数，自动管理 commit/rollback
    - run_in_session() 只管理 session 的创建和关闭，事务由调用方控制

    为什么不在这里自动 commit：
    调用方可能只需要读数据（无需 commit），也可能需要分多次 commit，
    事务策略因场景而异，统一在这里 commit 反而会限制灵活性。

    使用示例::

        # 读操作：无需 commit
        result = await run_in_session(
            lambda db: SomeService(db).query_something()
        )

        # 写操作：在回调内自行 commit
        async def _write(db: AsyncSession):
            svc = SomeService(db)
            await svc.save_something()
            await db.commit()

        await run_in_session(_write)
    """
    # 从全局工厂创建独立 session，不与 FastAPI 请求共享生命周期
    db = get_session_factory()()
    try:
        return await fn(db)
    finally:
        # 无论回调成功还是异常，都确保 session 被关闭、连接归还连接池
        await db.close()
