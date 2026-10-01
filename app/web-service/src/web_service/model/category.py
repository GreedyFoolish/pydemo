from typing import TYPE_CHECKING
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from web_service.model.association import product_category
from web_service.model.base import Base, IDMixin

if TYPE_CHECKING:
    # 避免循环导入问题，使用 TYPE_CHECKING 条件导入类型提示所需的类。
    from web_service.model.product import Product


class Category(Base, IDMixin):

    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text, default="")

    # 多对多关系：category.products → 该类别下所有产品
    # 通过 product_category 中间表关联，back_populates 关联 Product.categories
    products: Mapped[list["Product"]] = relationship(
        secondary=product_category, back_populates="categories"
    )
