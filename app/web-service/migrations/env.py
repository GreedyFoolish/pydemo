"""
Alembic 数据库迁移环境配置。

职责：
- 为 Alembic 提供数据库连接 URL（从项目 config.db_settings 读取）
- 注册所有 ORM 模型到 target_metadata，使 autogenerate 能检测到表结构变化

与 core/database.py 的区别：
- 本模块构造的是同步 URL（postgresql+psycopg2://），因为 Alembic 迁移是同步执行的
- core/database.py 构造的是异步 URL（postgresql+asyncpg://），用于 FastAPI 应用运行时
"""

import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from pathlib import Path
from alembic import context

# ---------------------------------------------------------------------------
# 1. 路径设置：src-layout 项目需要把 src/ 加入 sys.path
# ---------------------------------------------------------------------------
# alembic.ini 中 prepend_sys_path = . 指向 app/web-service/
# 但 web_service 包实际在 app/web-service/src/web_service/
# 因此需要手动把 src/ 目录加入 sys.path，否则 import 会失败
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_SRC_DIR))

# ---------------------------------------------------------------------------
# 2. 导入项目配置和模型
# ---------------------------------------------------------------------------
from web_service.core.config import db_settings

# 顺带触发 model/__init__.py，注册所有子模块的模型
from web_service.model.base import Base

# ---------------------------------------------------------------------------
# 3. 构造同步数据库连接 URL（Alembic 迁移使用同步驱动 psycopg2）
# ---------------------------------------------------------------------------
_sync_url = (
    f"postgresql+psycopg2://{db_settings.user}:{db_settings.password}"
    f"@{db_settings.host}:{db_settings.port}/{db_settings.name}"
)

# ---------------------------------------------------------------------------
# 4. Alembic 核心配置
# ---------------------------------------------------------------------------
config = context.config

# 把构造好的同步 URL 注入 alembic config，覆盖 alembic.ini 中的 sqlalchemy.url 占位
config.set_main_option("sqlalchemy.url", _sync_url)

# 配置 Python 日志（从 alembic.ini 读取日志配置）
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 所有已注册到 Base 的表元数据，autogenerate 通过对比它和实际数据库来生成迁移脚本
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线迁移模式：不连接实际数据库，直接输出 SQL 脚本。"""

    # 通过 config.get_main_option() 获取 sqlalchemy.url 配置
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        # target_metadata 用于 autogenerate 检测表结构变化
        target_metadata=target_metadata,
        # literal_binds=True 表示在生成 SQL 脚本时，把参数直接嵌入 SQL，而不是使用占位符
        literal_binds=True,
        # dialect_opts={"paramstyle": "named"} 表示使用命名参数风格（:name），而不是位置参数（?）
        dialect_opts={"paramstyle": "named"},
    )

    # context.begin_transaction() 表示在一个事务中执行迁移，确保迁移操作的原子性
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线迁移模式：连接实际数据库执行迁移。"""

    connectable = engine_from_config(
        # 从 alembic.ini 中读取 sqlalchemy.* 配置项，构造 SQLAlchemy Engine
        config.get_section(config.config_ini_section, {}),
        # 前缀 sqlalchemy. 表示只读取以 sqlalchemy. 开头的配置项
        prefix="sqlalchemy.",
        # poolclass=pool.NullPool 表示不使用连接池，每次迁移都新建连接，迁移完成后立即关闭
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # context.configure() 告诉 Alembic 使用这个连接和目标元数据
        context.configure(connection=connection, target_metadata=target_metadata)

        # context.begin_transaction() 表示在一个事务中执行迁移，确保迁移操作的原子性
        with context.begin_transaction():
            context.run_migrations()


# 根据运行模式选择离线或在线迁移
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
