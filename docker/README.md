# Docker 部署指南

web-service 容器化构建与运行说明。

## 目录结构

```
docker/
├── Dockerfile       # 多阶段构建（builder + runtime）
└── README.md        # 本文档
```

构建上下文（Build context）为仓库根目录，Dockerfile 中所有 COPY 路径均相对于根目录。

## 构建镜像

在仓库根目录执行：

```bash
docker build -f docker/Dockerfile -t fastapi-demo:latest .
```


| 参数                     | 含义                                          |
| ------------------------ | --------------------------------------------- |
| `-f docker/Dockerfile`   | 指定 Dockerfile 路径（相对于 build context）  |
| `-t fastapi-demo:latest` | 镜像名和 tag，可自定义如`fastapi-demo:v0.1.0` |
| `.`                      | build context 为当前目录（仓库根目录）        |

### 构建原理


| 阶段        | 基础镜像           | 做什么                                                                                      |
| ----------- | ------------------ | ------------------------------------------------------------------------------------------- |
| **builder** | `python:3.14-slim` | `pip install uv` + `uv sync`（阿里云 PyPI）从源码构建 workspace 所有包，装进 venv            |
| **runtime** | `python:3.14-slim` | 仅从 builder 复制 venv + 源码 + 迁移脚本，不带任何构建工具，体积最小                        |

### 镜像源策略


| 用途                  | 使用的源                            | 原因                                                                       |
| --------------------- | ----------------------------------- | -------------------------------------------------------------------------- |
| pip install uv        | `mirrors.aliyun.com/pypi`（阿里）   | 清华 PyPI 存在包同步不完整问题，多次返回 403 Forbidden                     |
| uv sync               | `mirrors.aliyun.com/pypi`（阿里）   | 同上；不从清华下载 wheel，但仍校验 `uv.lock` 中的 hash，版本锁定安全不受影响 |
| Docker 基础镜像       | Docker Desktop 配置的 registry-mirrors | 不走此 Dockerfile                                                          |

### 加速机制

- **BuildKit mount cache**：`pip install` 和 `uv sync` 的下载缓存在多次构建间保留，首次构建后二次构建秒级完成
- **严格锁定**：虽然去掉 `--frozen`（因为 lock 里的 wheel URL 指向清华，会 403），但 uv 仍校验 `uv.lock` 中的 hash，确保版本与官方一致

### 常用构建变体

```bash
# 只构建 runtime 阶段（调试用）
docker build -f docker/Dockerfile --target runtime -t fastapi-demo:latest .

# 强制无缓存构建（生产发布 / 构建不生效时使用）
docker build --no-cache -f docker/Dockerfile -t fastapi-demo:v0.1.0 .

# 网络有问题时，让构建直接用宿主机网络
docker build --network=host -f docker/Dockerfile -t fastapi-demo:latest .
```

## 运行容器

### 最简方式

```bash
docker run -d -p 9090:8000 --env-file .env fastapi-demo:latest
```

### 完整参数示例

```bash
docker run -d \
  --name fastapi-demo \
  -p 9090:8000 \
  --env-file .env.prod \
  --restart unless-stopped \
  --memory=512m \
  --cpus=1 \
  fastapi-demo:latest

# cmd 中只能单行输入
docker run -d --name fastapi-demo -p 9090:8000 --env-file .env.prod --restart unless-stopped --memory=512m --cpus=1 fastapi-demo:latest
```

### DB_HOST 关键说明

容器里的 `localhost` 就是容器自己，**永远连不上宿主机或其他容器上的 PostgreSQL**。`DB_HOST` 必须设为：

| 场景                                | DB_HOST 值                                | 说明                                     |
| ----------------------------------- | ----------------------------------------- | ---------------------------------------- |
| DB 跑在宿主机（Windows/macOS）上    | `host.docker.internal`                    | Docker Desktop 内置 DNS，指向宿主机 IP   |
| DB 跑在同一个 `docker-compose` 里   | DB 服务的容器名，如 `db`                  | `depends_on` 保证 DB 先启动              |
| DB 是独立容器，加入了自定义 network | DB 容器名，如 `pg16`                      | 自定义 network 支持容器名 DNS            |
| DB 在远程服务器                      | 服务器 IP，如 `192.168.1.10`              | 确保网络互通、防火墙放通                 |

### 参数说明


| 参数                                 | 含义                                                                              |
| ------------------------------------ | --------------------------------------------------------------------------------- |
| `-d`                                 | 后台运行（detached），不占用当前终端                                              |
| `--name fastapi-demo`                | 容器名称，后续`docker logs fastapi-demo`、`docker stop fastapi-demo` 都用这个名字 |
| `-p 9090:8000`                       | 端口映射，`宿主机端口:容器端口`。容器内固定为 8000，左边可以改                    |
| `-e`                                 | 设置单个环境变量，格式`-e KEY=VALUE`，优先级高于 `--env-file`                     |
| `--env-file .env`                    | 从文件批量注入环境变量，内容与项目`.env` 格式一致                                 |
| `-v /data/uploads:/app/data/uploads` | 数据卷挂载，把宿主机目录映射进容器，防止上传文件丢失                              |
| `--restart unless-stopped`           | 容器异常退出时自动重启（手动`docker stop` 不会被拉起来）                          |
| `--memory=512m`                      | 限制容器最多只能使用 512MB 内存，防止单个容器耗尽宿主机所有资源                   |
| `--cpus=1`                           | 限制容器最多只能使用 1 个 CPU 核心，防止单个容器耗尽宿主机所有资源                |

### 环境变量

容器启动时通过 `--env-file` 或 `-e KEY=VALUE` 注入，与项目 `.env` 配置完全一致：


| 变量              | 示例值                                   | 说明                                       |
| ----------------- | ---------------------------------------- | ------------------------------------------ |
| `DB_HOST`         | `host.docker.internal` 或 `db` 或 IP     | PostgreSQL 主机名/IP，**容器内不能用 localhost** |
| `DB_PORT`         | `5432`                                   | PostgreSQL 端口，默认`5432`                |
| `DB_USER`         | `admin`                                  | 数据库用户名                               |
| `DB_PASSWORD`     | `123123`                                 | 数据库密码                                 |
| `DB_NAME`         | `web_service`                            | 数据库名称                                 |
| `CORS_ORIGINS`    | `["http://localhost:3000"]`              | 跨域允许的源，JSON 数组                    |
| `AUTH_SECRET_KEY` | `xxx`                                    | JWT 签名密钥（生产环境务必用强随机字符串） |
| `LOG_LEVEL`       | `INFO`                                   | 日志级别                                   |
| `AI_API_KEY`      | `sk-xxx`                                 | AI 大模型 API Key                          |
| `AI_BASE_URL`     | `https://api.deepseek.com`               | AI 接口地址                                |
| `AI_MODEL`        | `deepseek-v4-flash`                      | 使用的模型名称                             |

## 启动流程

容器启动后，由 `CMD ["sh", "-c", "... && ..."]` 按以下顺序执行，任何一步失败容器会退出：

```
容器启动
  │
  ▼
① 执行 Alembic 迁移
   alembic -c /app/app/web-service/alembic.ini upgrade head
   把数据库升级到最新版本
  │
  ▼
② 启动 uvicorn 服务
   uvicorn web_service.main:app --host 0.0.0.0 --port 8000
```

**注意**：容器启动时会**立刻**执行迁移，没有 DB 就绪等待。如果 DB 还没起来，容器会 crash 并重启。推荐用 `docker compose` + `depends_on` 保证 DB 先启动。

## 常用运维命令

```bash
# 查看实时日志
docker logs -f fastapi-demo

# 查看最近 100 行
docker logs --tail 100 fastapi-demo

# 进入容器调试（用 sh，因为 runtime 没装 bash）
docker exec -it fastapi-demo sh

# 手动触发迁移（在容器内执行）
docker exec -it fastapi-demo alembic -c /app/app/web-service/alembic.ini upgrade head

# 停掉服务
docker stop fastapi-demo

# 重启（会重新走迁移 → 启动流程）
docker restart fastapi-demo
```

## 常见问题

### Q: 构建时 uv 下载很慢或报 403？

Dockerfile 已配置阿里云 PyPI 源。如果网络仍然慢，可以在 `docker build` 时追加 `--network=host`：

```bash
docker build --network=host -f docker/Dockerfile -t fastapi-demo:latest .
```

### Q: 容器启动几秒后就退出了？

用 `docker logs fastapi-demo` 看报错。最常见原因：

1. **DB 连不上** — 日志里有 `connection refused`、`Is the server running on that host`。检查 `DB_HOST` 是否正确（见上方 DB_HOST 关键说明）
2. **Alembic 迁移失败** — DB 里已经有表但版本不一致，手动 `docker exec -it fastapi-demo sh` 进去排查

### Q: 换了代码但构建没生效？

因为有 BuildKit mount cache，依赖层会复用。如果确认是源码问题，强制无缓存构建：

```bash
docker build --no-cache -f docker/Dockerfile -t fastapi-demo:latest .
```

如果只是改了一两个文件，正常构建就行 —— `COPY` 层会因为文件变了而失效，后面的层会自动重跑。
