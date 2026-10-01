from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import String, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from web_service.model.base import Base, IDMixin

if TYPE_CHECKING:
    # 避免循环导入问题，使用 TYPE_CHECKING 条件导入类型提示所需的类。
    from web_service.model.product import Product


class Sku(Base, IDMixin):

    # 外键关联到 Product 模型，表示该 SKU 属于哪个产品。使用 CASCADE 删除策略，当产品被删除时，相关的 SKU 也会被删除。
    product_id: Mapped[int] = mapped_column(
        ForeignKey("product.id", ondelete="CASCADE")
    )
    sku_code: Mapped[str] = mapped_column(String(50), unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)
    attrs: Mapped[dict] = mapped_column(JSONB)
    image_url: Mapped[str] = mapped_column(String)

    # 多对一关系：sku.product → 所属产品
    # back_populates 关联 Product.skus，实现双向导航
    product: Mapped["Product"] = relationship(back_populates="skus")
