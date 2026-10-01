from typing import TYPE_CHECKING
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from web_service.model.association import product_category
from web_service.model.base import Base, IDMixin, TimestampMixin

if TYPE_CHECKING:
    # 避免循环导入问题，使用 TYPE_CHECKING 条件导入类型提示所需的类。
    from web_service.model.category import Category
    from web_service.model.sku import Sku


class Product(Base, IDMixin, TimestampMixin):

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    brand: Mapped[str | None] = mapped_column(String(100))

    # 多对多关系：product.categories → 所属类别列表
    # 通过 product_category 中间表关联，back_populates 关联 Category.products
    categories: Mapped[list["Category"]] = relationship(
        secondary=product_category, back_populates="products"
    )
    # 一对多关系：product.skus → 该产品下所有 SKU
    # back_populates 关联 Sku.product，实现双向导航
    skus: Mapped[list["Sku"]] = relationship(back_populates="product")
