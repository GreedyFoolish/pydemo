from sqlalchemy import Column, ForeignKey, Table
from web_service.model.base import Base

product_category = Table(
    "product_category",
    Base.metadata,
    Column("product_id", ForeignKey("product.id"), primary_key=True),
    Column("category_id", ForeignKey("category.id"), primary_key=True),
)
