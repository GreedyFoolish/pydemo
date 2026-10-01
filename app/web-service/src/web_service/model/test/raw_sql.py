"""
原生 SQL 示例模块，展示如何使用 SQLAlchemy 执行原生 SQL。

本模块提供了以下功能：
- 直接使用 SQL 字符串插入数据。
- 按关键字搜索商品，对比 SQL 注入风险与参数化查询的安全写法。
- 按 ID 删除商品，同样展示拼接 vs 参数化两种写法。

适用场景：
- 需要执行复杂的 SQL 查询，ORM 无法满足需求时。
- 需要进行性能优化，直接使用原生 SQL 可能比 ORM 更高效时。

缺点：
- 开发效率低：需要手动编写 SQL 语句，缺少 ORM 的便利性。
- 易出错：手动拼接 SQL 语句容易出现语法错误或逻辑错误。
- 注入风险：如果直接拼接用户输入的参数，可能导致 SQL 注入攻击。
- 适配性差：原生 SQL 语法可能依赖特定数据库方言，跨数据库迁移时需要改写。
"""

from sqlalchemy import text
from web_service.core.database import get_engine


async def raw_sql_insert():
    """直接用 SQL 字符串插入数据"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO product (name, description, brand) VALUES ('iPhone 16', '最新款智能手机', 'Apple')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO product (name, description, brand) VALUES ('iPhone 15', '上一代旗舰', 'Apple')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO product (name, description, brand) VALUES ('Galaxy S25', '三星旗舰', 'Samsung')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO product (name, description, brand) VALUES ('Xiaomi 15', '性价比之选', 'Xiaomi')"
            )
        )
    print("数据插入完成")


async def search_products(keyword: str):
    engine = get_engine()
    async with engine.connect() as conn:
        """按关键字搜索商品——接受用户输入，拼接 SQL, 可能导致 SQL 注入"""
        # sql = f"SELECT * FROM product WHERE name LIKE '%{keyword}%'"
        # result = await conn.execute(text(sql))
        """按关键字搜索商品——参数化绑定，安全"""
        result = await conn.execute(
            text("SELECT * FROM product WHERE name LIKE :keyword"),
            {"keyword": f"%{keyword}%"},
        )
        rows = result.fetchall()
        for row in rows:
            print(f"  [{row.id}] {row.name} - {row.brand}")


async def delete_product_by_id(product_id: str):
    engine = get_engine()
    async with engine.begin() as conn:
        """按 ID 删除商品——接受用户输入，拼接 SQL，可能导致 SQL 注入"""
        # sql = f"DELETE FROM product WHERE id = {product_id}"
        # await conn.execute(text(sql))
        """按 ID 删除商品——参数化绑定，安全"""
        await conn.execute(
            text("DELETE FROM product WHERE id = :id"),
            {"id": product_id},
        )
    print(f"删除完成，id={product_id}")


async def test_raw_sql():
    await raw_sql_insert()
    # 查询所有数据
    # await search_products("")
    # 正常查询
    print("=== 搜索 'iPhone' ===")
    await search_products("iPhone")
    # SQL 注入示例
    # await search_products("%' OR 1=1; --")
    # 正常删除
    print("=== 删除 id=1 ===")
    await delete_product_by_id(1)
    # SQL 注入示例
    # await delete_product_by_id("1 OR 1=1; --")
    print("=== 再次搜索 'iPhone' ===")
    await search_products("iPhone")
