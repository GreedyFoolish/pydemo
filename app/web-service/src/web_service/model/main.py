import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# 异步连接字符串格式：postgresql+asyncpg://用户名:密码@主机:端口/数据库名
DATABASE_URL = "postgresql+asyncpg://admin:123123@localhost:5432/web_service"


async def test_connection():
    # 创建异步引擎
    config = {
        "pool_size": 10,  # 连接池维持的连接数
        "max_overflow": 20,  # 池满后额外可创建的连接数
        "pool_pre_ping": True,  # 每次连接前检查是否存活
        "echo": False,  # 是否打印 SQL 日志
    }
    engine = create_async_engine(DATABASE_URL, **config)

    try:
        # 测试连接：执行一个简单的查询
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            # 获取结果(第一行第一列)
            value = result.scalar()
            print(f"✅ 异步连接 PostgreSQL 成功！查询结果: {value}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
    finally:
        # 关闭引擎，释放资源
        await engine.dispose()


# 运行异步函数
if __name__ == "__main__":
    asyncio.run(test_connection())
