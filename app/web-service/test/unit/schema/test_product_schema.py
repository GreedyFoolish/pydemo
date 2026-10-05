"""Product Schema 单元测试。

覆盖 ProductCreate / ProductUpdate / ProductResponse / ProductResponseDetail
的字段约束、默认值、from_attributes 行为。
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from decimal import Decimal

from web_service.schema.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductResponseDetail,
)


# ============================================================
# ProductCreate 测试
# ============================================================


class TestProductCreate:
    """ProductCreate 字段校验测试。"""

    def test_valid_minimal_input(self):
        """最小合法输入：仅必填字段 name。"""
        schema = ProductCreate(name="测试产品")
        assert schema.name == "测试产品"
        assert schema.description == ""
        assert schema.brand is None
        assert schema.category_ids == []

    def test_valid_full_input(self):
        """完整合法输入。"""
        schema = ProductCreate(
            name="完整产品",
            description="详细描述",
            brand="TestBrand",
            category_ids=[1, 2, 3],
        )
        assert schema.name == "完整产品"
        assert schema.description == "详细描述"
        assert schema.brand == "TestBrand"
        assert schema.category_ids == [1, 2, 3]

    @pytest.mark.parametrize(
        "name_value",
        [
            "",  # 空串触发 min_length=1
            "x" * 201,  # 超过 max_length=200
        ],
    )
    def test_name_validation_errors(self, name_value):
        """name 字段边界校验。"""
        with pytest.raises(ValidationError):
            ProductCreate(name=name_value)

    def test_name_boundary_max(self):
        """name 恰好 200 字符应该通过。"""
        schema = ProductCreate(name="x" * 200)
        assert len(schema.name) == 200

    @pytest.mark.parametrize(
        "brand_value",
        [
            "",  # 空串触发 min_length=1
            "x" * 101,  # 超过 max_length=100
        ],
    )
    def test_brand_validation_errors(self, brand_value):
        """brand 字段边界校验。"""
        with pytest.raises(ValidationError):
            ProductCreate(name="测试", brand=brand_value)

    def test_brand_boundary_max(self):
        """brand 恰好 100 字符应该通过。"""
        schema = ProductCreate(name="测试", brand="x" * 100)
        assert len(schema.brand) == 100

    def test_brand_none_is_valid(self):
        """brand=None 是合法的（可选字段）。"""
        schema = ProductCreate(name="测试", brand=None)
        assert schema.brand is None

    def test_description_default_empty(self):
        """description 缺省值为空串。"""
        schema = ProductCreate(name="测试")
        assert schema.description == ""

    def test_description_max_length(self):
        """description 超过 2000 字符应失败。"""
        with pytest.raises(ValidationError):
            ProductCreate(name="测试", description="x" * 2001)

    def test_description_boundary_max(self):
        """description 恰好 2000 字符应该通过。"""
        schema = ProductCreate(name="测试", description="x" * 2000)
        assert len(schema.description) == 2000

    def test_category_ids_default_empty_list(self):
        """category_ids 缺省值为空列表。"""
        schema = ProductCreate(name="测试")
        assert schema.category_ids == []

    def test_extra_fields_ignored(self):
        """BaseSchema.extra='ignore'：多余字段不触发错误。"""
        schema = ProductCreate(name="测试", unknown_field=123)
        assert not hasattr(schema, "unknown_field")


# ============================================================
# ProductUpdate 测试
# ============================================================


class TestProductUpdate:
    """ProductUpdate 部分更新测试。"""

    def test_empty_is_valid(self):
        """所有字段都缺省也是合法的（支持空更新）。"""
        schema = ProductUpdate()
        assert schema.name is None
        assert schema.description is None
        assert schema.brand is None
        assert schema.category_ids is None

    def test_partial_update_name_only(self):
        """只更新 name。"""
        schema = ProductUpdate(name="新名称")
        assert schema.name == "新名称"
        assert schema.brand is None

    def test_name_validation_rules_same_as_create(self):
        """ProductUpdate 的 name 校验规则应与 ProductCreate 一致。"""
        with pytest.raises(ValidationError):
            ProductUpdate(name="")
        with pytest.raises(ValidationError):
            ProductUpdate(name="x" * 201)

    def test_brand_empty_string_invalid(self):
        """空字符串触发 min_length=1。"""
        with pytest.raises(ValidationError):
            ProductUpdate(brand="")

    def test_extra_fields_ignored(self):
        """多余字段被忽略。"""
        schema = ProductUpdate(name="测试", extra=1)
        assert not hasattr(schema, "extra")


# ============================================================
# ProductResponse 测试
# ============================================================


class TestProductResponse:
    """ProductResponse 响应 DTO 测试。"""

    def test_valid_input(self):
        now = datetime.now()
        schema = ProductResponse(
            id=1,
            name="测试",
            description="描述",
            brand="B",
            created_at=now,
            updated_at=now,
        )
        assert schema.id == 1
        assert schema.name == "测试"
        assert schema.created_at == now

    def test_brand_default_none(self):
        """brand 缺省为 None。"""
        now = datetime.now()
        schema = ProductResponse(
            id=1,
            name="测试",
            created_at=now,
            updated_at=now,
        )
        assert schema.brand is None

    def test_description_default_empty(self):
        """description 缺省为空串。"""
        now = datetime.now()
        schema = ProductResponse(
            id=1,
            name="测试",
            created_at=now,
            updated_at=now,
        )
        assert schema.description == ""

    def test_from_attributes(self):
        """测试 from_attributes=True：可以从 ORM 对象构造。"""
        from unittest.mock import MagicMock

        orm_obj = MagicMock()
        orm_obj.id = 1
        orm_obj.name = "ORM产品"
        orm_obj.description = "ORM描述"
        orm_obj.brand = "ORMBrand"
        orm_obj.created_at = datetime(2024, 1, 1)
        orm_obj.updated_at = datetime(2024, 1, 2)

        schema = ProductResponse.model_validate(orm_obj)
        assert schema.id == 1
        assert schema.name == "ORM产品"

    def test_extra_fields_ignored(self):
        """extra='ignore' 生效。"""
        now = datetime.now()
        schema = ProductResponse(
            id=1,
            name="测试",
            created_at=now,
            updated_at=now,
            unknown=123,
        )
        assert not hasattr(schema, "unknown")


# ============================================================
# ProductResponseDetail 测试
# ============================================================


class TestProductResponseDetail:
    """ProductResponseDetail 包含关联对象的详细响应测试。"""

    def test_default_empty_associations(self):
        """关联字段缺省为空列表。"""
        now = datetime.now()
        schema = ProductResponseDetail(
            id=1,
            name="测试",
            created_at=now,
            updated_at=now,
        )
        assert schema.categories == []
        assert schema.skus == []

    def test_with_associations(self):
        """携带分类和 SKU 关联数据。"""
        from web_service.schema.category import CategoryResponse
        from web_service.schema.sku import SkuResponse

        now = datetime.now()
        cat = CategoryResponse(id=1, name="分类A")
        sku = SkuResponse(
            id=1,
            product_id=1,
            sku_code="SKU001",
            price=Decimal("99.99"),
            attrs={"color": "red"},
            image_url="http://img.png",
        )

        schema = ProductResponseDetail(
            id=1,
            name="测试",
            created_at=now,
            updated_at=now,
            categories=[cat],
            skus=[sku],
        )
        assert len(schema.categories) == 1
        assert schema.categories[0].name == "分类A"
        assert len(schema.skus) == 1
        assert schema.skus[0].sku_code == "SKU001"
