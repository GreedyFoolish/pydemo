from sqlalchemy import select, insert, update, delete
from web_service.model.engine import get_engine
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
