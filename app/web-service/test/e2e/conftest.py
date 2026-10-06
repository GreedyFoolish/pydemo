"""
pytest 测试配置文件。

在 pytest 会话级别完成以下工作：
1. 创建独立的测试数据库（避免污染开发/生产库）
2. 通过 alembic 执行迁移创建表结构
3. 启动 FastAPI 测试服务器（供 e2e 测试使用）

每个测试用例执行后会 TRUNCATE 所有表并重置自增序列，
确保用例之间数据完全隔离，互不影响。
"""

import asyncio
import os
import time
import subprocess
import pytest
import psycopg2
from pathlib import Path
from contextlib import contextmanager
from dotenv import load_dotenv

# pydantic-settings 在首次实例化 _DBSettings 时读取 DB_NAME 环境变量，
# 因此必须在 import db_settings 之前强制覆盖，才能让 db_settings.name 正确指向测试库
# 注意：必须用赋值而非 setdefault，因为 pytest 进程启动时 DB_NAME 可能已存在于系统环境变量中，
# setdefault 不会覆盖已存在的值，会导致误连开发库
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent.parent / ".env.test")
os.environ["DB_NAME"] = "web_e2e_test_service"
from web_service.core.config import _DBSettings

db_settings = _DBSettings()

# 测试服务器运行端口，避开常见的 8000/8080 等端口，防止冲突
TEST_SERVER_PORT = "18000"

# 全局变量，用于追踪子进程和日志文件句柄，以便在会话结束时清理
_server_process: subprocess.Popen | None = None
_log_file = None


# PostgreSQL 管理操作辅助函数
@contextmanager
def _create_cur():
    """创建一个指向 PostgreSQL 默认库 (postgres) 的同步 psycopg2 连接。

    DROP DATABASE / CREATE DATABASE 等管理操作不能在目标库连接上执行，
    因此需要连接到 postgres 默认库作为中介。
    """
    conn = psycopg2.connect(
        host=db_settings.host,
        port=db_settings.port,
        user=db_settings.user,
        password=db_settings.password,
        dbname="postgres",
    )
    # 自动提交模式下 DROP/CREATE DATABASE 无需显式 commit
    conn.autocommit = True
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()
        conn.close()


# 测试服务器生命周期
def _start_server():
    """启动 FastAPI 测试服务器作为子进程。

    使用 `fastapi dev` 热重载模式，方便调试；
    轮询等待 /docs 端点返回 200，确认服务器就绪后才返回。
    """
    global _server_process, _log_file

    # 将子进程输出重定向到 tmp/test_server.log，避免与 pytest 输出混淆
    tmp_dir = Path(__file__).resolve().parent.parent.parent.parent / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    _log_file = open(tmp_dir / "test_server.log", "w")

    # 显式传递 env=os.environ.copy()，确保子进程拿到 pytest 进程中
    # 已设置的 DB_NAME=web_e2e_test_service；否则子进程可能回退到 .env 中的 web_service
    child_env = os.environ.copy()
    child_env["DB_NAME"] = "web_e2e_test_service"

    # 直接用 uvicorn 启动，去掉 --reload：测试不需要热重载，
    # 且 --reload 在 Windows 上会额外启动 reloader 子进程，
    # 可能破坏 env 参数传递链路，导致 DB_NAME 回退到 .env 的值
    _server_process = subprocess.Popen(
        [
            "uv",
            "run",
            "--package",
            "web-service",
            # "fastapi",
            # "dev",
            # "app/web-service/src/web_service/main.py",
            "uvicorn",
            "web_service.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            TEST_SERVER_PORT,
        ],
        stdout=_log_file,
        stderr=subprocess.STDOUT,
        env=child_env,
    )

    # 轮询等待服务器就绪：最多约 150 * 0.1s = 15 秒
    # 冷启动需要加载 Python 模块 + uvicorn + asyncpg 连接池，
    # 只 ping /docs 静态端点不代表 DB 连接池已就绪，
    # 改用 GET /api/products 确保整条链路（服务器 + 数据库）都可用
    import httpx

    for _ in range(150):
        try:
            resp = httpx.get(f"http://localhost:{TEST_SERVER_PORT}/docs")
            if resp.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError("测试服务器启动超时，请检查 tmp/test_server.log")


def _stop_server():
    """终止测试服务器子进程并关闭日志文件。"""
    global _server_process, _log_file
    if _server_process is not None:
        _server_process.terminate()
        _server_process.wait(timeout=10)
        _server_process = None
    if _log_file is not None:
        _log_file.close()
        _log_file = None


def _kill_port_if_occupied(port: int):
    """检查指定端口是否被残留进程占用，如果是则强制杀掉。

    上一轮测试如果 uvicorn 子进程未正常退出（如 pytest 进程被 kill、
    超时退出等），会变成孤儿进程继续占用端口，导致新一轮测试启动
    新 uvicorn 时端口冲突或连接到旧进程持有旧的数据库连接。
    这个函数在 pytest_sessionstart 开头调用，确保端口干净。
    """
    import socket
    import subprocess

    # 先用 socket bind 检测端口是否空闲
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        sock.close()
        return  # 端口空闲，无需处理
    except OSError:
        sock.close()

    # 端口被占用，用 netstat 找到占用进程并强制杀掉
    result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if f":{port}" in line and "LISTENING" in line:
            pid = line.strip().split()[-1]
            print(f"[conftest] 发现端口 {port} 被 PID {pid} 占用，正在终止残留进程...")
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
            time.sleep(1)  # 等待端口释放
            break


# pytest 会话级钩子：创建/销毁测试数据库 + 启动/关闭服务器
def pytest_sessionstart(session):
    """pytest 会话开始时执行：重建测试数据库 + alembic 迁移 + 启动服务器。"""
    # 第零步：检查并清理残留进程（防止上一轮测试遗留的 uvicorn 孤儿进程）
    _kill_port_if_occupied(int(TEST_SERVER_PORT))

    with _create_cur() as cur:
        # 第一步：终止所有到测试库的后端连接
        # PostgreSQL 不允许 DROP DATABASE 时仍有活跃连接，必须先强制断开
        cur.execute(
            f"SELECT pg_terminate_backend(pg_stat_activity.pid) "
            f"FROM pg_stat_activity "
            f"WHERE pg_stat_activity.datname = '{db_settings.name}' "
            f"AND pid <> pg_backend_pid()"
        )
        # 第二步：删除旧库（如果存在）并创建新库
        cur.execute(f"DROP DATABASE IF EXISTS {db_settings.name}")
        cur.execute(f"CREATE DATABASE {db_settings.name}")

    # 第三步：使用 alembic 迁移在新库中创建表结构
    from alembic.config import Config
    from alembic import command

    WEB_SERVICE_DIR = Path(__file__).resolve().parent.parent.parent
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(WEB_SERVICE_DIR / "migrations"))
    alembic_cfg.set_main_option(
        "sqlalchemy.url",
        f"postgresql://{db_settings.user}:{db_settings.password}@{db_settings.host}:{db_settings.port}/{db_settings.name}",
    )
    command.upgrade(alembic_cfg, "head")

    # 第四步：启动 FastAPI 测试服务器
    # uvicorn 子进程的 lifespan 会自动跑 init_settings 写入系统配置种子。
    # 由于 _force_cleanup 已跳过 settinggroup/settingitem 表，种子只会在
    # 测试库创建时（pytest_sessionstart）需要写入一次，后续再也不会被清。
    _start_server()


def pytest_collection_modifyitems(config, items):
    """调整用例执行顺序：带 skip_cleanup marker 的用例排最前。

    cleanup_db 是 autouse 的，每个用例跑前都会 TRUNCATE 所有表。
    把依赖种子的 skip_cleanup 用例排最前，先于其他文件的 TRUNCATE 跑。
    """
    skip_cleanup_items = [i for i in items if i.get_closest_marker("skip_cleanup")]
    normal_items = [i for i in items if not i.get_closest_marker("skip_cleanup")]
    if skip_cleanup_items:
        items[:] = skip_cleanup_items + normal_items


def pytest_sessionfinish(session, exitstatus):
    """pytest 会话结束时执行：关闭服务器 + 清理测试数据库。"""
    _stop_server()

    with _create_cur() as cur:
        # 同样先终止活跃连接再 DROP，确保即使服务器未正常关闭也能清理成功
        cur.execute(
            f"SELECT pg_terminate_backend(pg_stat_activity.pid) "
            f"FROM pg_stat_activity "
            f"WHERE pg_stat_activity.datname = '{db_settings.name}' "
            f"AND pid <> pg_backend_pid()"
        )
        cur.execute(f"DROP DATABASE IF EXISTS {db_settings.name}")


# pytest Fixtures
@pytest.fixture(scope="session")
def event_loop():
    """为整个 pytest 会话提供共享事件循环。

    pytest-asyncio 在 pyproject.toml 配置了 asyncio_mode = "auto"，
    但显式提供 session 级事件循环可避免多循环场景下的资源冲突。
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def base_url():
    """测试服务器的 base URL，供需要自行拼接完整 URL 的用例使用。"""
    return f"http://localhost:{TEST_SERVER_PORT}"


@pytest.fixture
async def async_client():
    """HTTP 异步客户端 fixture。

    供 e2e 测试使用，通过 HTTP 请求测试完整的 API 链路。
    使用 `async with` 自动管理连接生命周期，每次请求后立即关闭连接。
    """
    from httpx import AsyncClient

    async with AsyncClient(base_url=f"http://localhost:{TEST_SERVER_PORT}") as client:
        yield client


# TRUNCATE 时跳过的表：系统配置种子数据，由 pytest_sessionstart 统一初始化一次
_SKIP_TABLES = {"settinggroup", "settingitem"}


async def _force_cleanup(max_retries: int = 3):
    """强制清理数据库：TRUNCATE 业务表并重置自增序列。

    跳过 setting_group / setting_item 表，保留种子数据供所有用例共享。

    实现要点：
    - TRUNCATE 前先 pg_terminate_backend 杀掉 uvicorn 连接池中到测试库的
      所有连接。PostgreSQL 的 TRUNCATE 需要 ACCESS EXCLUSIVE 锁，和所有其他
      锁级别冲突。uvicorn 连接池里的连接即使在 session commit 后，也可能
      因为某些原因（如连接池 check、autovacuum、异步响应收尾等）短暂持有
      锁，导致 TRUNCATE 间歇地阻塞或 ConnectionDoesNotExistError。
      pg_terminate_backend 是最可靠的解法——杀完立即 TRUNCATE，然后
      uvicorn 的 pool_pre_ping 会自动重建连接，无状态丢失风险。
    - 使用 NullPool 独立引擎：cleanup 操作使用独立的数据库连接，不依赖
      uvicorn 的连接池，避免清理操作被 uvicorn 的锁阻塞。
    - 按外键依赖的反向顺序 TRUNCATE + CASCADE：避免 FK 约束冲突。
    - 加重试逻辑：在网络波动或极端锁竞争场景下（如 pg_terminate_backend
      之后、TRUNCATE 之前有新的连接瞬间建立），重试可兜底。
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from web_service.model.base import Base

    url = (
        f"postgresql+asyncpg://{db_settings.user}:{db_settings.password}"
        f"@{db_settings.host}:{db_settings.port}/{db_settings.name}"
    )

    last_error = None
    for attempt in range(1, max_retries + 1):
        engine = create_async_engine(url, poolclass=NullPool, echo=False)
        try:
            # 第 1 步：杀掉 uvicorn 连接池中到测试库的所有连接
            # pid <> pg_backend_pid() 避免杀掉当前 NullPool 引擎自己的连接
            async with engine.connect() as conn:
                await conn.execute(
                    text(
                        f"SELECT pg_terminate_backend(pid) "
                        f"FROM pg_stat_activity "
                        f"WHERE datname = '{db_settings.name}' "
                        f"AND pid <> pg_backend_pid()"
                    )
                )
                await conn.commit()

            # 给 PostgreSQL 一点时间完成连接清理
            await asyncio.sleep(0.05)

            # 第 2 步：TRUNCATE 业务表（跳过系统配置表）
            async with engine.begin() as conn:
                # 按外键依赖的反向顺序 TRUNCATE，避免 FK 约束冲突
                for table in reversed(Base.metadata.sorted_tables):
                    if table.name in _SKIP_TABLES:
                        continue
                    await conn.execute(
                        text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE')
                    )

            await engine.dispose()
            return  # 成功，直接返回

        except Exception as e:
            last_error = e
            await engine.dispose()
            if attempt < max_retries:
                # 指数退避：50ms → 100ms → 200ms
                await asyncio.sleep(0.05 * (2 ** (attempt - 1)))

    raise RuntimeError(
        f"_force_cleanup 在 {max_retries} 次重试后仍然失败: {last_error}"
    )


@pytest.fixture(autouse=True)
async def cleanup_db(async_client, request):
    """autouse fixture：每个测试用例**前后**都清理数据库（双保险）。

    - 测试前先清理：确保无论上一个测试的清理是否完全成功，
      当前测试都从干净状态开始
    - 测试后再清理：防止数据残留影响后续测试
    - 依赖 async_client：确保 HTTP 客户端在清理前已关闭连接
    - skip_cleanup marker：依赖 lifespan / pytest_sessionstart 主动
      写入种子的用例跳过清理
    """
    if request.node.get_closest_marker("skip_cleanup"):
        yield
        return

    # 测试执行前：先清理一次，确保数据干净
    await _force_cleanup()

    yield

    # 测试执行后：再清理一次，防止数据残留
    await _force_cleanup()
