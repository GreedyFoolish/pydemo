"""
数据库模块。

提供异步引擎和 Session 工厂的懒加载单例管理。
- get_engine(): 返回全局唯一的 AsyncEngine 实例
- get_session_factory(): 返回全局唯一的 async_sessionmaker 实例
"""

from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from web_service.core.config import db_settings

# 全局单例引擎，首次调用 get_engine() 时初始化
_engine: AsyncEngine | None = None


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
            echo=False,  # 关闭 SQL 日志输出
        )

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
