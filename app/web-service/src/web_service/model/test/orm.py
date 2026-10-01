"""
ORM 示例，展示 SQLAlchemy ORM 的四种基本操作：
1. 插入：创建模型对象，session.add() 加入会话。
2. 查询：select() 构造查询，scalars()/scalar_one() 获取对象。
3. 更新：查出对象后直接修改属性，提交时自动生成 UPDATE。
4. 删除：查出对象后 session.delete()，提交时自动生成 DELETE。

与 Core 表达式 / 原生 SQL 的区别：
- ORM 操作的是 Python 对象，不需要手写 SQL 或表达式。
- Session 自动追踪对象状态的变化（脏检查），提交时生成对应 SQL。
- 插入和删除使用 begin() 自动提交；查询使用普通 session_factory() 手动管理。
"""

from sqlalchemy import select
from web_service.core.database import get_session_factory
from web_service.model.product import Product
from web_service.model.category import Category

# 全局 Session 工厂单例，复用 core.database 的统一实例
session_factory = get_session_factory()


async def orm_insert():
    """ORM 插入——创建模型对象，session.add() 加入会话，begin() 自动提交。"""
    async with session_factory.begin() as session:
        # 直接实例化模型类，字段作为构造参数
        product = Product(
            name="iPhone 16",
            description="最新款智能手机",
            brand="Apple",
        )
        session.add(product)

        product2 = Product(
            name="iPhone 15",
            description="上一代旗舰",
            brand="Apple",
        )
        session.add(product2)

        # Category 也通过相同方式插入
        category = Category(name="手机", description="移动通信设备")
        session.add(category)
        # begin() 退出时自动 commit，无需手动调用
    print("ORM 插入完成")


async def orm_query():
    """ORM 查询——select() 构造查询，scalars() 拿到模型对象列表。

    使用普通 async with session（非 begin），查询不需要提交事务。
    """
    async with session_factory() as session:
        # select(Product) 生成 SELECT * FROM product，where() 加过滤条件
        stmt = select(Product).where(Product.name.like("%iPhone%"))
        result = await session.execute(stmt)
        # scalars() 从 Row 中提取第一列（即 Product 模型实例）
        products = result.scalars().all()
        for p in products:
            print(f"  [{p.id}] {p.name} - {p.brand}")


async def orm_update():
    """ORM 更新——查出对象，直接修改 Python 属性，Session 脏检查自动生成 UPDATE。"""
    async with session_factory.begin() as session:
        # scalar_one() 期望恰好返回一条记录，多条或零条会抛异常
        stmt = select(Product).where(Product.id == 1)
        result = await session.execute(stmt)
        product = result.scalar_one()
        # 直接赋值属性，Session 会标记该对象为「脏」，提交时自动生成 UPDATE
        product.name = "iPhone 16 Pro"
    print("ORM 更新完成")


async def orm_delete():
    """ORM 删除——查出对象，调用 session.delete()，提交时自动生成 DELETE。"""
    async with session_factory.begin() as session:
        stmt = select(Product).where(Product.id == 2)
        result = await session.execute(stmt)
        product = result.scalar_one()
        # delete() 标记该对象为待删除，提交时生成 DELETE FROM ... WHERE id = ?
        await session.delete(product)
    print("ORM 删除完成")


async def test_orm():
    """串联插入→查询→更新→查询→删除→查询的完整演示流程。"""
    await orm_insert()
    print("=== 查询 ===")
    await orm_query()
    await orm_update()
    print("=== 查询（更新后） ===")
    await orm_query()
    await orm_delete()
    print("=== 查询（删除后） ===")
    await orm_query()
