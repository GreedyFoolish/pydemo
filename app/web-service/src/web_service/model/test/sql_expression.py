"""
SQL 表达式示例模块，展示如何使用 SQLAlchemy 的 Core 表达式语言进行数据库操作。

Core 表达式语言是 SQLAlchemy 介于 ORM 和原生 SQL 之间的查询构建方式：
- 比原生 SQL 更安全：自动参数化，无注入风险
- 比 ORM 更灵活：直接操作表和列，不受对象映射约束

本模块提供了以下功能：
- 使用 Core 表达式插入数据。
- 使用 Core 表达式查询数据。
- 使用 Core 表达式更新数据。
- 使用 Core 表达式删除数据。

适用场景：
- 需要复杂查询（如多表联查、聚合）但不想写原生 SQL 时。
- 需要细粒度控制 SQL 生成，但又想利用 SQLAlchemy 的跨方言适配能力时。

优点：
- 类型化：Core 表达式语言提供了类型化的查询构建方式，减少了 SQL 注入风险。
- 更接近 SQL：Core 表达式语言提供了类似 SQL 的操作方式，便于理解和使用。
- 安全性：Core 表达式语言自动处理参数化查询，减少 SQL 注入风险。

缺点：
- 学习曲线：需同时理解 SQL 概念和 Core 的 API 语法。
- 代码量：相比 ORM，Core 表达式语言可能需要编写更多的代码来实现相同的功能。
- 无对象映射：返回的是 Row 对象，不具备 ORM 模型的便利性。
"""

from sqlalchemy import select, insert, update, delete
from web_service.core.database import get_engine
from web_service.model.category import Category
from web_service.model.product import Product


async def core_insert():
    """Core 表达式插入"""
    engine = get_engine()
    async with engine.begin() as conn:
        # insert() 返回 Insert 对象，values() 设置列值
        stmt = insert(Product).values(
            name="iPhone 16",
            description="最新款智能手机",
            brand="Apple",
        )
        await conn.execute(stmt)

        stmt = insert(Product).values(
            name="iPhone 15",
            description="上一代旗舰",
            brand="Apple",
        )
        await conn.execute(stmt)

        stmt = insert(Category).values(name="手机", description="移动通信设备")
        await conn.execute(stmt)
    print("Core 插入完成")


async def core_query():
    """Core 表达式查询"""
    engine = get_engine()
    async with engine.connect() as conn:
        # select() 返回 Select 对象
        # where() 用 Python 表达式构建条件——Python 的 == 而非 SQL 的 =
        stmt = select(Product).where(Product.name.like("%iPhone%"))
        result = await conn.execute(stmt)
        for row in result:
            print(f"  [{row.id}] {row.name} - {row.brand}")


async def core_update():
    """Core 表达式更新"""
    engine = get_engine()
    async with engine.begin() as conn:
        stmt = update(Product).where(Product.id == 1).values(name="iPhone 16 Pro")
        await conn.execute(stmt)
    print("Core 更新完成")


async def core_delete():
    """Core 表达式删除"""
    engine = get_engine()
    async with engine.begin() as conn:
        stmt = delete(Product).where(Product.id == 2)
        await conn.execute(stmt)
    print("Core 删除完成")


async def test_sql_expression():
    await core_insert()
    print("=== 查询 ===")
    await core_query()
    await core_update()
    print("=== 查询（更新后） ===")
    await core_query()
    await core_delete()
    print("=== 查询（删除后） ===")
    await core_query()
