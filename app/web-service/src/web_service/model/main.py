"""拉取代码配置好 .env 文件后，根目录运行 uv sync --project web-service 命令，即可直接进行数据库连接测试，确保数据库配置正确。"""

import asyncio
from sqlalchemy import text
from web_service.core.database import get_engine
from web_service.model.base import Base
from web_service.model.category import Category
from web_service.model.product import Product
from web_service.model.sku import Sku
from web_service.model.test.raw_sql import test_raw_sql
from web_service.model.test.sql_expression import test_sql_expression
from web_service.model.test.session_maker import test_session_maker
from web_service.model.test.orm import test_orm


async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表创建完成")


async def test_connection():
    engine = get_engine()
    try:
        # 测试连接：执行一个简单的查询
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            # 获取结果(第一行第一列)
            value = result.scalar()
            print(f"异步连接 PostgreSQL 成功！查询结果: {value}")
    except Exception as e:
        print(f"连接失败: {e}")
    finally:
        # 关闭引擎，释放资源
        await engine.dispose()


async def main():
    await init_db()
    # await test_connection()
    # await test_raw_sql()
    # await test_sql_expression()
    # await test_session_maker()
    await test_orm()


# 运行异步函数
if __name__ == "__main__":
    asyncio.run(main())
