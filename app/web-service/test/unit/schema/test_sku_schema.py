"""SKU Schema 单元测试。

覆盖 SkuCreate / SkuUpdate / SkuResponse / SkuResponseDetail
的 Decimal price 精度校验、product_id 外键约束、attrs JSON 字段。
"""

import pytest
from decimal import Decimal
from pydantic import ValidationError

from web_service.schema.sku import (
    SkuCreate,
    SkuUpdate,
    SkuResponse,
    SkuResponseDetail,
)


def _make_sku_create_kwargs(**overrides):
    """构造 SkuCreate 的默认合法关键字参数。"""
    base = {
        "product_id": 1,
        "sku_code": "SKU-TEST-001",
        "price": Decimal("99.99"),
        "stock": 10,
        "attrs": {"color": "red", "size": "M"},
        "image_url": "http://example.com/image.png",
    }
    base.update(overrides)
    return base


# ============================================================
# SkuCreate 测试
# ============================================================


class TestSkuCreate:
    """SkuCreate 字段校验测试。"""

    def test_valid_minimal_input(self):
        """完整合法输入。"""
        kw = _make_sku_create_kwargs()
        schema = SkuCreate(**kw)
        assert schema.product_id == 1
        assert schema.sku_code == "SKU-TEST-001"
        assert schema.price == Decimal("99.99")
        assert schema.stock == 10
        assert schema.attrs == {"color": "red", "size": "M"}
        assert schema.image_url == "http://example.com/image.png"

    # --- product_id ---

    @pytest.mark.parametrize("pid", [0, -1])
    def test_product_id_must_be_positive(self, pid):
        """product_id <= 0 触发 gt=0 校验。"""
        with pytest.raises(ValidationError):
            SkuCreate(**_make_sku_create_kwargs(product_id=pid))

    # --- sku_code ---

    @pytest.mark.parametrize(
        "code_value",
        [
            "",  # min_length=1
            "x" * 51,  # max_length=50
        ],
    )
    def test_sku_code_validation(self, code_value):
        """sku_code 长度边界校验。"""
        with pytest.raises(ValidationError):
            SkuCreate(**_make_sku_create_kwargs(sku_code=code_value))

    def test_sku_code_boundary(self):
        """恰好 50 字符通过。"""
        schema = SkuCreate(**_make_sku_create_kwargs(sku_code="x" * 50))
        assert len(schema.sku_code) == 50

    # --- price ---

    def test_price_zero_rejected(self):
        """price <= 0 触发 gt=0。"""
        with pytest.raises(ValidationError):
            SkuCreate(**_make_sku_create_kwargs(price=Decimal("0")))

    def test_price_negative_rejected(self):
        with pytest.raises(ValidationError):
            SkuCreate(**_make_sku_create_kwargs(price=Decimal("-1")))

    def test_price_max_digits(self):
        """超过 max_digits=12 的价格被拒绝。"""
        # 12 位 + 小数 = 超过 12 位整数部分
        with pytest.raises(ValidationError):
            SkuCreate(**_make_sku_create_kwargs(price=Decimal("1234567890123")))

    def test_price_decimal_places(self):
        """超过 decimal_places=2 被拒绝。"""
        with pytest.raises(ValidationError):
            SkuCreate(**_make_sku_create_kwargs(price=Decimal("99.999")))

    def test_price_valid_decimal(self):
        """合法小数位数。"""
        schema = SkuCreate(**_make_sku_create_kwargs(price=Decimal("99.99")))
        assert schema.price == Decimal("99.99")

    def test_price_integer_is_valid(self):
        """整数价格（无小数）也通过。"""
        schema = SkuCreate(**_make_sku_create_kwargs(price=Decimal("100")))
        assert schema.price == Decimal("100")

    # --- stock ---

    def test_stock_negative_rejected(self):
        """stock < 0 触发 ge=0。"""
        with pytest.raises(ValidationError):
            SkuCreate(**_make_sku_create_kwargs(stock=-1))

    def test_stock_zero_valid(self):
        """stock=0 通过。"""
        schema = SkuCreate(**_make_sku_create_kwargs(stock=0))
        assert schema.stock == 0

    def test_stock_default_zero(self):
        """stock 缺省为 0。"""
        kw = _make_sku_create_kwargs()
        kw.pop("stock")
        schema = SkuCreate(**kw)
        assert schema.stock == 0

    # --- attrs ---

    def test_attrs_must_be_dict(self):
        """attrs 不是 dict 时失败。"""
        with pytest.raises(ValidationError):
            SkuCreate(**_make_sku_create_kwargs(attrs=["not", "dict"]))

    def test_attrs_empty_dict_valid(self):
        """空 dict 合法。"""
        schema = SkuCreate(**_make_sku_create_kwargs(attrs={}))
        assert schema.attrs == {}

    # --- image_url ---

    @pytest.mark.parametrize(
        "url_value",
        [
            "",  # min_length=1
            "x" * 501,  # max_length=500
        ],
    )
    def test_image_url_validation(self, url_value):
        with pytest.raises(ValidationError):
            SkuCreate(**_make_sku_create_kwargs(image_url=url_value))

    def test_image_url_boundary(self):
        """恰好 500 字符通过。"""
        schema = SkuCreate(**_make_sku_create_kwargs(image_url="x" * 500))
        assert len(schema.image_url) == 500

    # --- extra fields ---

    def test_extra_fields_ignored(self):
        """多余字段被忽略。"""
        kw = _make_sku_create_kwargs()
        kw["extra"] = 1
        schema = SkuCreate(**kw)
        assert not hasattr(schema, "extra")


# ============================================================
# SkuUpdate 测试
# ============================================================


class TestSkuUpdate:
    """SkuUpdate 部分更新测试。"""

    def test_empty_is_valid(self):
        """所有字段为 None 合法。"""
        schema = SkuUpdate()
        assert schema.sku_code is None
        assert schema.price is None
        assert schema.stock is None
        assert schema.attrs is None
        assert schema.image_url is None

    def test_partial_stock_only(self):
        """只更新 stock。"""
        schema = SkuUpdate(stock=100)
        assert schema.stock == 100
        assert schema.price is None

    def test_sku_code_validation(self):
        """空串触发 min_length=1。"""
        with pytest.raises(ValidationError):
            SkuUpdate(sku_code="")

    def test_price_zero_rejected(self):
        with pytest.raises(ValidationError):
            SkuUpdate(price=Decimal("0"))

    def test_stock_negative_rejected(self):
        with pytest.raises(ValidationError):
            SkuUpdate(stock=-1)


# ============================================================
# SkuResponse 测试
# ============================================================


class TestSkuResponse:
    """SkuResponse 响应 DTO 测试。"""

    def test_valid_input(self):
        schema = SkuResponse(
            id=1,
            product_id=10,
            sku_code="SKU001",
            price=Decimal("49.99"),
            stock=5,
            attrs={"color": "blue"},
            image_url="http://img.png",
        )
        assert schema.id == 1
        assert schema.product_id == 10
        assert schema.price == Decimal("49.99")

    def test_stock_default_zero(self):
        schema = SkuResponse(
            id=1,
            product_id=10,
            sku_code="SKU001",
            price=Decimal("49.99"),
            attrs={},
            image_url="http://img.png",
        )
        assert schema.stock == 0

    def test_from_attributes(self):
        """from_attributes=True：从 ORM 对象构造。"""
        from unittest.mock import MagicMock

        orm_obj = MagicMock()
        orm_obj.id = 1
        orm_obj.product_id = 10
        orm_obj.sku_code = "ORM-SKU"
        orm_obj.price = Decimal("1.00")
        orm_obj.stock = 3
        orm_obj.attrs = {"k": "v"}
        orm_obj.image_url = "http://orm.png"

        schema = SkuResponse.model_validate(orm_obj)
        assert schema.sku_code == "ORM-SKU"
        assert schema.price == Decimal("1.00")


# ============================================================
# SkuResponseDetail 测试
# ============================================================


class TestSkuResponseDetail:
    """SkuResponseDetail 包含 product 关联的详细响应测试。"""

    def test_product_default_none(self):
        """product 缺省为 None。"""
        schema = SkuResponseDetail(
            id=1,
            product_id=10,
            sku_code="SKU001",
            price=Decimal("10"),
            attrs={},
            image_url="http://img.png",
        )
        assert schema.product is None

    def test_with_product_forward_ref(self):
        """携带 product 关联数据，验证前向引用解析。"""
        from datetime import datetime
        from web_service.schema.product import ProductResponse

        now = datetime.now()
        product = ProductResponse(
            id=10,
            name="关联产品",
            created_at=now,
            updated_at=now,
        )
        schema = SkuResponseDetail(
            id=1,
            product_id=10,
            sku_code="SKU001",
            price=Decimal("10"),
            attrs={},
            image_url="http://img.png",
            product=product,
        )
        assert schema.product is not None
        assert schema.product.name == "关联产品"
