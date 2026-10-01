首先，运行下面命令增加`alembic`和`psycopg2-binary`依赖。

```
# 安装 alembic 和 psycopg2-binary 依赖
uv add --package web-service alembic==1.18.4 psycopg2-binary==2.9.12
```

进入`/app/web-service`目录，运行下面命令初始化数据库迁移。

````
# 初始化数据库迁移
uv run alembic init migrations
````

初始化完成后，对`env.py`文件进行调整，实现数据库迁移逻辑代码。

完成数据库迁移逻辑代码后，执行生成迁移脚本命令。

```
# 生成迁移脚本
make db-migrate message="init"

# 执行迁移
make db-upgrade

# 执行回滚
make db-downgrade version=-1         # 回退一步
make db-downgrade version=abc123     # 回退到指定版本
```
