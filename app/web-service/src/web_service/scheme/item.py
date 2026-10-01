from pydantic import BaseModel, Field


class Item(BaseModel):
    # ✅ 带默认值的可选字段
    item_id: int | None = Field(
        default=None,  # 默认值
        title="商品ID",  # 标题
        description="商品的唯一标识符，在创建商品时可忽略，系统会自动生成。",  # 描述
        ge=1,  # 大于等于1
        examples=[1, 2, 3],  # 示例值列表
    )

    # ✅ 必填字段的写法
    name: str = Field(
        ...,  # 三个点表示必填
        title="商品名称",
        description="商品的显示名称，长度必须在2到10个字符之间。",
        min_length=2,
        max_length=10,
        examples=["无线鼠标"],
    )

    # ✅ 带默认值的价格字段
    price: float = Field(
        default=0.0,  # 默认值
        title="商品价格",
        description="商品的销售价格，必须大于或等于0。",
        ge=0.0,
        examples=[19.99, 0.0, 100.5],  # 示例值列表
    )
