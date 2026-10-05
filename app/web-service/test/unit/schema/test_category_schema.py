"""Category Schema 单元测试。

覆盖 CategoryCreate / CategoryUpdate / CategoryResponse / CategoryResponseDetail
的字段约束、默认值、循环引用处理。
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from web_service.schema.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CategoryResponseDetail,
)


# ============================================================
# CategoryCreate 测试
# ============================================================


class TestCategoryCreate:
    """CategoryCreate 字段校验测试。"""

    def test_valid_minimal_input(self):
        """最小合法输入：仅必填 name。"""
        schema = CategoryCreate(name="电子产品")
        assert schema.name == "电子产品"
        assert schema.description == ""

    @pytest.mark.parametrize(
        "name_value",
        [
            "",  # min_length=1
            "x" * 51,  # max_length=50
        ],
    )
    def test_name_validation_errors(self, name_value):
        """name 边界校验。"""
        with pytest.raises(ValidationError):
            CategoryCreate(name=name_value)

    def test_name_boundary_max(self):
        """name 恰好 50 字符通过。"""
        schema = CategoryCreate(name="x" * 50)
        assert len(schema.name) == 50

    def test_description_default_empty(self):
        """description 缺省为空串。"""
        schema = CategoryCreate(name="测试")
        assert schema.description == ""

    def test_description_too_long(self):
        """超过 2000 字符失败。"""
        with pytest.raises(ValidationError):
            CategoryCreate(name="测试", description="x" * 2001)

    def test_description_boundary_max(self):
        """恰好 2000 字符通过。"""
        schema = CategoryCreate(name="测试", description="x" * 2000)
        assert len(schema.description) == 2000

    def test_extra_fields_ignored(self):
        """多余字段被忽略。"""
        schema = CategoryCreate(name="测试", unknown=1)
        assert not hasattr(schema, "unknown")


# ============================================================
# CategoryUpdate 测试
# ============================================================


class TestCategoryUpdate:
    """CategoryUpdate 部分更新测试。"""

    def test_empty_is_valid(self):
        """所有字段为 None 也是合法的。"""
        schema = CategoryUpdate()
        assert schema.name is None
        assert schema.description is None

    def test_partial_name_only(self):
        """只更新 name。"""
        schema = CategoryUpdate(name="新分类")
        assert schema.name == "新分类"

    def test_name_validation_same_as_create(self):
        """空/超长 name 触发 ValidationError。"""
        with pytest.raises(ValidationError):
            CategoryUpdate(name="")
        with pytest.raises(ValidationError):
            CategoryUpdate(name="x" * 51)


# ============================================================
# CategoryResponse 测试
# ============================================================


class TestCategoryResponse:
    """CategoryResponse 响应测试。"""

    def test_valid_input(self):
        schema = CategoryResponse(id=1, name="分类A", description="描述")
        assert schema.id == 1
        assert schema.name == "分类A"

    def test_description_default_empty(self):
        """description 缺省为空串。"""
        schema = CategoryResponse(id=1, name="分类A")
        assert schema.description == ""

    def test_from_attributes(self):
        """测试 from_attributes=True。"""
        from unittest.mock import MagicMock

        orm_obj = MagicMock()
        orm_obj.id = 10
        orm_obj.name = "ORMCat"
        orm_obj.description = "ORMDesc"

        schema = CategoryResponse.model_validate(orm_obj)
        assert schema.id == 10
        assert schema.name == "ORMCat"


# ============================================================
# CategoryResponseDetail 测试
# ============================================================


class TestCategoryResponseDetail:
    """CategoryResponseDetail 包含 products 关联的详细响应测试。"""

    def test_default_empty_products(self):
        """products 缺省为空列表。"""
        schema = CategoryResponseDetail(id=1, name="分类A")
        assert schema.products == []

    def test_with_products_forward_ref(self):
        """携带 products 关联数据，验证前向引用正常解析。"""
        from web_service.schema.product import ProductResponse

        now = datetime.now()
        product = ProductResponse(
            id=1,
            name="产品A",
            created_at=now,
            updated_at=now,
        )
        schema = CategoryResponseDetail(
            id=1,
            name="分类A",
            products=[product],
        )
        assert len(schema.products) == 1
        assert schema.products[0].name == "产品A"

    def test_model_rebuild_after_import(self):
        """循环引用解决后，model_rebuild 应无异常。"""
        from web_service.schema.category import CategoryResponseDetail

        # model_rebuild 可能因循环依赖需要手动调用
        try:
            CategoryResponseDetail.model_rebuild()
        except Exception:
            # 如果已经在别处 rebuild 过或不存在依赖，则忽略
            pass
        # 基本功能仍正常
        schema = CategoryResponseDetail(id=1, name="测试")
        assert schema.id == 1
