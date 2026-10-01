"""
SQLAlchemy ORM 基础模型定义。

本模块为数据库模型提供基类和混入类，包括：
- 基础声明基类
- ID 混入类（用于主键）
- 时间戳混入类（用于创建/更新时间）
"""

from datetime import datetime
from sqlalchemy import DateTime, Identity, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的统一基类。

    子类继承后自动获得两项能力：
    1. SQLAlchemy 的 ORM 映射机制（继承自 DeclarativeBase）
    2. 自动以小写类名作为表名，子类无需手动声明 __tablename__
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        # 钩子方法：SQLAlchemy 构建映射时自动调用，将类名小写化作为表名
        return cls.__name__.lower()


class IDMixin:
    """为模型提供自增主键 id 的混入类。

    不单独使用，需与 Base 组合继承，例如：
        class Category(Base, IDMixin): ...
    """

    # 自增主键列，使用数据库的 identity 功能自动生成。
    id: Mapped[int] = mapped_column(Identity(), primary_key=True)


class TimestampMixin:
    """为模型提供创建/更新时间戳的混入类。

    不单独使用，需与 Base 组合继承，例如：
        class Product(Base, IDMixin, TimestampMixin): ...
    两列均在数据库侧自动维护，应用层无需手动赋值。
    """

    # 记录创建时的时间戳。在记录首次创建时自动设置为当前时间。
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # 记录最后更新时的时间戳。在记录创建时自动设置为当前时间，并在记录修改时自动更新。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
