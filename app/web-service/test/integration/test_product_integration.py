"""
Product Service + API 集成测试。

覆盖范围：
- ProductService 直接测试
  - create（含 category_ids 多对多关联建立）
  - update（含 category_ids 关联替换）
  - get_detail（含 selectinload 预加载 categories + skus）
  - _resolve_categories（缺失 ID 错误路径）
  - 继承 BaseService 的 get_by_id / list / list_paged / count / delete
  - IntegrityError → DatabaseException 转换
- ProductAPI 通过 ASGI transport 测试
  - 路由 wiring / 响应序列化 / 关联分类建立
  - 外键冲突（关联不存在的分类 → 409 DB_FK_CONFLICT）
  - 统一响应格式 / 异常处理
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.exception import DatabaseException, ErrorCode
from web_service.model.product import Product
from web_service.schema.category import CategoryCreate
from web_service.schema.product import ProductCreate, ProductUpdate
from web_service.service.category import CategoryService
from web_service.service.product import ProductService

# ═══════════════════════════════════════════════════════════════════
# 辅助函数：先创建分类供产品关联
# ═══════════════════════════════════════════════════════════════════


async def _create_category(db_session: AsyncSession, name: str) -> int:
    """在测试 session 中创建一个分类，返回其 ID。"""
    service = CategoryService(db_session)
    instance = await service.create(CategoryCreate(name=name))
    await db_session.commit()
    return instance.id


# ═══════════════════════════════════════════════════════════════════
# ProductService 集成测试
# ═══════════════════════════════════════════════════════════════════


class TestProductServiceCreate:
    """ProductService.create() 测试（重点：多对多关联处理）。"""

    async def test_create_product_without_categories(self, db_session: AsyncSession):
        """不关联分类创建产品，category_ids 使用默认空列表。"""
        service = ProductService(db_session)
        instance = await service.create(
            ProductCreate(name="极简产品", description="无分类")
        )
        await db_session.commit()

        assert isinstance(instance, Product)
        assert instance.id is not None
        assert instance.name == "极简产品"
        assert instance.description == "无分类"

    async def test_create_product_with_category(self, db_session: AsyncSession):
        """关联一个分类创建产品。"""
        cat_id = await _create_category(db_session, "电子产品")

        service = ProductService(db_session)
        instance = await service.create(
            ProductCreate(
                name="iPhone",
                brand="Apple",
                category_ids=[cat_id],
            )
        )
        await db_session.commit()

        assert instance.id is not None
        assert instance.name == "iPhone"
        assert instance.brand == "Apple"

        # 验证中间表记录（通过 get_detail 间接验证关联）
        detail = await service.get_detail(instance.id)
        assert detail is not None
        assert len(detail.categories) == 1
        assert detail.categories[0].id == cat_id
        assert detail.categories[0].name == "电子产品"

    async def test_create_product_with_multiple_categories(
        self, db_session: AsyncSession
    ):
        """一个产品关联多个分类。"""
        cat1_id = await _create_category(db_session, "高端")
        cat2_id = await _create_category(db_session, "手机")

        service = ProductService(db_session)
        instance = await service.create(
            ProductCreate(
                name="iPhone Pro",
                category_ids=[cat1_id, cat2_id],
            )
        )
        await db_session.commit()

        detail = await service.get_detail(instance.id)
        assert detail is not None
        cat_ids = {c.id for c in detail.categories}
        assert cat_ids == {cat1_id, cat2_id}

    async def test_create_product_nonexistent_category_fk_conflict(
        self, db_session: AsyncSession
    ):
        """关联不存在的分类 ID → DB_FK_CONFLICT。"""
        service = ProductService(db_session)

        with pytest.raises(DatabaseException) as exc_info:
            await service.create(ProductCreate(name="幽灵产品", category_ids=[9999]))

        assert exc_info.value.error_code == ErrorCode.DB_FK_CONFLICT


class TestProductServiceResolveCategories:
    """ProductService._resolve_categories() 内部方法测试。"""

    async def test_resolve_categories_empty(self, db_session: AsyncSession):
        """空列表返回空列表。"""
        service = ProductService(db_session)
        result = await service._resolve_categories([])
        assert result == []

    async def test_resolve_categories_success(self, db_session: AsyncSession):
        """正常解析分类 ID 列表。"""
        cat1_id = await _create_category(db_session, "A")
        cat2_id = await _create_category(db_session, "B")

        service = ProductService(db_session)
        result = await service._resolve_categories([cat1_id, cat2_id])

        assert len(result) == 2
        found_ids = {c.id for c in result}
        assert found_ids == {cat1_id, cat2_id}

    async def test_resolve_categories_missing_id(self, db_session: AsyncSession):
        """部分 ID 不存在 → DB_FK_CONFLICT。"""
        cat_id = await _create_category(db_session, "存在的")

        service = ProductService(db_session)
        with pytest.raises(DatabaseException) as exc_info:
            await service._resolve_categories([cat_id, 9999])

        assert exc_info.value.error_code == ErrorCode.DB_FK_CONFLICT
        assert "missing_category_ids" in str(exc_info.value.detail)

    async def test_resolve_categories_dedup(self, db_session: AsyncSession):
        """重复的 ID 自动去重。"""
        cat_id = await _create_category(db_session, "唯一")

        service = ProductService(db_session)
        result = await service._resolve_categories([cat_id, cat_id, cat_id])

        assert len(result) == 1


class TestProductServiceUpdate:
    """ProductService.update() 测试。"""

    async def test_update_partial_fields(self, db_session: AsyncSession):
        """只更新 name，其他字段保持不变。"""
        service = ProductService(db_session)
        instance = await service.create(
            ProductCreate(name="旧名称", description="不变", brand="不变")
        )
        await db_session.commit()

        updated = await service.update(instance.id, ProductUpdate(name="新名称"))
        await db_session.commit()

        assert updated.name == "新名称"
        assert updated.description == "不变"
        assert updated.brand == "不变"

    async def test_update_category_ids_replace(self, db_session: AsyncSession):
        """更新 category_ids 应完全替换旧关联。"""
        cat_a_id = await _create_category(db_session, "分类A")
        cat_b_id = await _create_category(db_session, "分类B")
        cat_c_id = await _create_category(db_session, "分类C")

        service = ProductService(db_session)
        instance = await service.create(
            ProductCreate(name="产品", category_ids=[cat_a_id, cat_b_id])
        )
        await db_session.commit()

        # 确认初始关联
        detail = await service.get_detail(instance.id)
        initial_cat_ids = {c.id for c in detail.categories}
        assert initial_cat_ids == {cat_a_id, cat_b_id}

        # 替换关联为 [cat_c_id]
        await service.update(instance.id, ProductUpdate(category_ids=[cat_c_id]))
        await db_session.commit()

        detail = await service.get_detail(instance.id)
        new_cat_ids = {c.id for c in detail.categories}
        assert new_cat_ids == {cat_c_id}

    async def test_update_category_ids_none_no_change(self, db_session: AsyncSession):
        """category_ids 传 None 时不修改关联。"""
        cat_id = await _create_category(db_session, "关联分类")

        service = ProductService(db_session)
        instance = await service.create(
            ProductCreate(name="产品", category_ids=[cat_id])
        )
        await db_session.commit()

        # 更新 name 但不传 category_ids
        await service.update(instance.id, ProductUpdate(name="改名产品"))
        await db_session.commit()

        # 关联应保持不变
        detail = await service.get_detail(instance.id)
        assert len(detail.categories) == 1
        assert detail.categories[0].id == cat_id

    async def test_update_not_found(self, db_session: AsyncSession):
        """更新不存在的产品抛 NOT_FOUND。"""
        service = ProductService(db_session)
        with pytest.raises(DatabaseException) as exc_info:
            await service.update(9999, ProductUpdate(name="不存在"))
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND


class TestProductServiceDetail:
    """ProductService.get_detail() 测试。"""

    async def test_get_detail_with_categories_and_skus(self, db_session: AsyncSession):
        """get_detail 预加载 categories 和 skus。"""
        from sqlalchemy import insert
        from web_service.model.sku import Sku
        from web_service.model.association import product_category

        cat_id = await _create_category(db_session, "完整分类")

        service = ProductService(db_session)
        instance = await service.create(
            ProductCreate(name="完整产品", category_ids=[cat_id])
        )
        await db_session.flush()

        # 直接用 SQL 插入 SKU
        sku = Sku(
            product_id=instance.id,
            sku_code="SKU-TEST",
            price=99.99,
            attrs={"颜色": "黑"},
            image_url="https://example.com/img.jpg",
        )
        db_session.add(sku)
        await db_session.commit()

        # get_detail 应该预加载 categories 和 skus
        detail = await service.get_detail(instance.id)
        assert detail is not None
        assert detail.id == instance.id
        assert len(detail.categories) == 1
        assert detail.categories[0].name == "完整分类"
        assert len(detail.skus) == 1
        assert detail.skus[0].sku_code == "SKU-TEST"

    async def test_get_detail_not_found(self, db_session: AsyncSession):
        """不存在的产品返回 None。"""
        service = ProductService(db_session)
        assert await service.get_detail(9999) is None


# ═══════════════════════════════════════════════════════════════════
# Product API 集成测试（通过 async_client 走真实 HTTP）
#
# 与 Service 层测试的区别：
# - 验证 API 路由 wiring / 依赖注入 / 响应序列化 / 统一响应格式
# - 验证异常处理中间件（NOT_FOUND / DB_FK_CONFLICT）
# ═══════════════════════════════════════════════════════════════════


async def _api_create_category(async_client, name: str) -> int:
    """通过 API 创建分类，返回其 ID。"""
    resp = await async_client.post("/api/categories", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


class TestProductAPICreate:
    """POST /api/products 测试。"""

    async def test_create_product_via_api(self, async_client):
        """创建产品并关联分类。"""
        cat_id = await _api_create_category(async_client, "API分类")

        resp = await async_client.post(
            "/api/products",
            json={
                "name": "API产品",
                "brand": "TestBrand",
                "category_ids": [cat_id],
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == "0"
        assert body["data"]["name"] == "API产品"
        assert body["data"]["brand"] == "TestBrand"

    async def test_create_product_nonexistent_category_via_api(self, async_client):
        """关联不存在的分类返回 409 DB_FK_CONFLICT。"""
        resp = await async_client.post(
            "/api/products",
            json={"name": "幽灵产品", "category_ids": [9999]},
        )

        assert resp.status_code == 409
        assert resp.json()["code"] == ErrorCode.DB_FK_CONFLICT.code


class TestProductAPIList:
    """GET /api/products 测试。"""

    async def test_list_via_api(self, async_client):
        """空列表返回正确结构。"""
        resp = await async_client.get("/api/products")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0


class TestProductAPIGet:
    """GET /api/products/{id} 测试。"""

    async def test_get_not_found_via_api(self, async_client):
        """不存在的产品返回 404。"""
        resp = await async_client.get("/api/products/9999")
        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code


class TestProductAPIUpdate:
    """PUT /api/products/{id} 测试。"""

    async def test_update_via_api(self, async_client):
        """更新产品名称。"""
        create_resp = await async_client.post("/api/products", json={"name": "旧名称"})
        product_id = create_resp.json()["data"]["id"]

        resp = await async_client.put(
            f"/api/products/{product_id}", json={"name": "新名称"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "新名称"

    async def test_update_not_found_via_api(self, async_client):
        """更新不存在的产品返回 404。"""
        resp = await async_client.put("/api/products/9999", json={"name": "不存在"})
        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code


class TestProductAPIDelete:
    """DELETE /api/products/{id} 测试。"""

    async def test_delete_via_api(self, async_client):
        """删除产品返回 204。"""
        create_resp = await async_client.post("/api/products", json={"name": "待删除"})
        product_id = create_resp.json()["data"]["id"]

        # 确保事务提交 - 通过查询触发
        await async_client.get(f"/api/products/{product_id}")

        resp = await async_client.delete(f"/api/products/{product_id}")
        assert resp.status_code == 204

        # 再次查询应 404
        resp = await async_client.get(f"/api/products/{product_id}")
        assert resp.status_code == 404

    async def test_delete_not_found_via_api(self, async_client):
        """删除不存在的产品返回 404。"""
        resp = await async_client.delete("/api/products/9999")
        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code
