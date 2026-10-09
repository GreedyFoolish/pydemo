# =============================================================================
# web-service Dockerfile —— 多阶段构建（builder + runtime）
# Build context: 仓库根目录（e:\workspace\todo\pydemo）
# BuildKit cache:   docker build --mount=type=cache  自动生效
# =============================================================================

# ---------------------------------------------------------------------------
# 阶段 1：builder —— 安装依赖
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS builder

# ---- 安装 uv（用 pip 从阿里 PyPI 安装，避免拉 ghcr.io 镜像过慢） ----
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install uv -i https://mirrors.aliyun.com/pypi/simple/

# ---- uv 环境变量 ----
# UV_INDEX_URL：阿里云 PyPI 源（清华镜像存在包同步不完整的问题，多次返回 403 Forbidden）
# UV_COMPILE_BYTECODE：安装时预编译 .pyc，减少运行时首次启动的编译开销
# UV_LINK_MODE=copy：强制复制文件而非硬链接/符号链接，否则 runtime 阶段 COPY --from=builder 会断链导致 venv 不可用
ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# ---- 一次性复制所有源码 + 配置 ----
COPY pyproject.toml uv.lock ./
COPY package/web-utils ./package/web-utils
COPY app/web-service ./app/web-service

# ---- 创建 venv 并安装所有依赖 ----
# 不使用 --frozen：因为 uv.lock 中的 wheel URL 来自清华镜像（存在 403 问题），
#     改为从 UV_INDEX_URL（阿里云）下载，但仍然校验 lock 中的 hash，
#     保证版本锁定的安全性不受影响
# --no-dev：排除 dev 依赖（测试/调试等运行时不需要的包）
# --no-editable：生产环境不使用可编辑模式，确保包真正装进 venv
# --all-packages：覆盖 workspace 全部成员（web-service + web-utils）
# --mount=type=cache,target=/root/.cache/uv：BuildKit 跨构建缓存，
#     首次构建后，后续构建直接复用已下载的 wheel / sdist，大幅加速
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv \
    && uv sync --no-dev --no-editable --all-packages

# ---------------------------------------------------------------------------
# 阶段 2：runtime —— 仅保留运行时所需的最小环境
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

WORKDIR /app

# ---- 从 builder 复制 venv ----
COPY --from=builder /app/.venv ./.venv

# ---- 从 builder 复制运行时需要的源码（src-layout） ----
COPY --from=builder /app/package/web-utils/src ./package/web-utils/src
COPY --from=builder /app/app/web-service/src ./app/web-service/src

# ---- 从 builder 复制迁移脚本 + alembic 配置 ----
COPY --from=builder /app/app/web-service/alembic.ini ./app/web-service/alembic.ini
COPY --from=builder /app/app/web-service/migrations ./app/web-service/migrations

# ---- 环境变量 ----
# PATH：确保 venv 内的 uvicorn / alembic 等可执行文件优先于系统 python
ENV PATH="/app/.venv/bin:$PATH" \
    # PYTHONPATH：src-layout 项目，显式把两个 src/ 加入 Python 搜索路径
    PYTHONPATH="/app/app/web-service/src:/app/package/web-utils/src" \
    # Python stdout/stderr 无缓冲，日志实时写入容器日志驱动
    PYTHONUNBUFFERED=1 \
    # 不写 .pyc 到磁盘，节省只读容器空间
    PYTHONDONTWRITEBYTECODE=1

# ---- 暴露端口 ----
EXPOSE 8000

# ---- 容器启动 ----
# python:3.14-slim 自带 dash (sh)，用 sh -c 顺序执行：
#   1. alembic 数据库迁移（DB 需已就绪，由外部 docker-compose depends_on 保证）
#   2. uvicorn 启动服务
CMD ["sh", "-c", "alembic -c /app/app/web-service/alembic.ini upgrade head && uvicorn web_service.main:app --host 0.0.0.0 --port 8000"]
