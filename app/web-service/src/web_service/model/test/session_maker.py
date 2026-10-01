"""
Session 工厂示例，展示了三种不同的 Session 使用方式：
1. 原始写法：Session 生命周期和事务全手动管理。
2. 实际推荐写法：Session 自动管理，事务手动控制。
3. 最简洁写法：Session 和事务全部自动管理。

适用场景：
- 原始写法：几乎不使用，仅作为对比展示。
- 实际推荐写法：适用于需要在一个 Session 中执行多步操作、根据中间结果决定是否提交的场景。
- 最简洁写法：适用于单步操作或无需中间决策的简单场景。

注意事项：
- Session 生命周期管理：使用 async with 确保 Session 在使用后自动关闭， 避免连接泄漏。
- 事务管理：根据业务需求选择手动或自动提交事务，确保数据一致性。
"""

from sqlalchemy import insert
from web_service.core.database import get_session_factory
from web_service.model.product import Product

session_factory = get_session_factory()


async def insert_with_session():
    """原始写法：Session 生命周期和事务全手动管理。

    手动 try/except/finally 关闭 Session，容易遗漏 close 导致连接泄漏。
    实际开发中几乎不使用，仅作为对比展示。
    """
    session = session_factory()
    try:
        stmt = insert(Product).values(
            name="iPhone 16",
            description="最新款智能手机",
            brand="Apple",
        )
        await session.execute(stmt)
        await session.commit()
    except:
        await session.rollback()
        raise
    finally:
        await session.close()
    print("提交完成")


async def insert_with_manual_commit():
    """实际推荐写法：Session 自动管理，事务手动控制。

    async with 自动 close（不会泄漏），commit/rollback 仍由代码决定。
    适用于需要在一个 Session 中执行多步操作、根据中间结果决定是否提交的场景。
    """
    async with session_factory() as session:
        try:
            stmt = insert(Product).values(
                name="iPhone 16",
                description="最新款智能手机",
                brand="Apple",
            )
            await session.execute(stmt)
            await session.commit()
        except:
            await session.rollback()
            raise
    print("手动提交完成")


async def insert_with_auto_commit():
    """最简洁写法：Session 和事务全部自动管理。

    session_factory.begin() 退出时自动 commit，异常时自动 rollback。
    适用于单步操作或无需中间决策的简单场景。
    """
    async with session_factory.begin() as session:
        stmt = insert(Product).values(
            name="iPhone 15",
            description="上一代旗舰",
            brand="Apple",
        )
        await session.execute(stmt)
    print("自动提交完成")


async def test_session_maker():
    await insert_with_session()
    await insert_with_manual_commit()
    await insert_with_auto_commit()
