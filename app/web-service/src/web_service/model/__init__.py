"""
使用如下命令在 docker 中创建 postgres 容器
docker run -d
  --name pg16
  -e POSTGRES_USER=admin
  -e POSTGRES_PASSWORD=123123
  -p 5432:5432
  -v "你的目录绝对路径:/var/lib/postgresql/data"
  postgres:16

绝对路径示例：E:/docker/workspace/db

使用如下命令在 docker 中创建 pgadmin4 容器
docker run -d
  --name pgadmin4
  -e PGADMIN_DEFAULT_EMAIL=admin@qq.com
  -e PGADMIN_DEFAULT_PASSWORD=123123
  -p 5050:80
  dpage/pgadmin4


创建 postgres 和 pgadmin4 容器成功后，启动容器（此时默认开启），然后访问 http://localhost:5050 进行数据库连接，进行数据库创建操作
"""

from web_service.model import (
    category,
    product,
    setting_group,
    setting_item,
    sku,
)
