import asyncio
from sqlalchemy import text
from web_service.model.engine import get_engine


async def test_connection():
    engine = get_engine()
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
