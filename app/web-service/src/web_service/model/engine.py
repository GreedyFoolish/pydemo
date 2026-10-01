"""
数据库引擎模块。

提供异步 PostgreSQL 连接引擎的单例管理，
通过 get_engine() 函数返回全局唯一的 AsyncEngine 实例。
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
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
