"""
Category Service + API 集成测试。

覆盖范围：
- CategoryService 直接测试（继承 BaseService 的通用 CRUD）
  - create / get_by_id / list / list_paged / count
  - update（部分更新语义）/ delete
  - get_detail（含 products 的 eager load）
  - _require_by_id 内部方法（不存在时抛 NOT_FOUND）
- CategoryAPI 通过 ASGI transport 测试
  - 路由 wiring / 依赖注入 / 响应序列化
  - 统一响应格式包装 / 错误码正确性
  - 异常处理（NOT_FOUND / VALIDATION_ERROR）
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.exception import DatabaseException, ErrorCode
from web_service.model.category import Category
from web_service.schema.category import (
    CategoryCreate,
    CategoryUpdate,
)
from web_service.service.category import CategoryService

# ═══════════════════════════════════════════════════════════════════
# CategoryService 集成测试
# ═══════════════════════════════════════════════════════════════════


class TestCategoryServiceCreate:
    """CategoryService.create() 测试。"""

    async def test_create_category_success(self, db_session: AsyncSession):
        """正常创建分类，返回 ORM 实例且 id 已分配。"""
        service = CategoryService(db_session)
        schema = CategoryCreate(name="电子产品", description="电子类商品")

        instance = await service.create(schema)
        await db_session.commit()

        assert isinstance(instance, Category)
        assert instance.id is not None
        assert instance.name == "电子产品"
        assert instance.description == "电子类商品"

    async def test_create_category_default_description(self, db_session: AsyncSession):
        """description 不传时使用空字符串默认值。"""
        service = CategoryService(db_session)
        schema = CategoryCreate(name="极简分类")

        instance = await service.create(schema)
        await db_session.commit()

        assert instance.description == ""


class TestCategoryServiceGetById:
    """CategoryService.get_by_id() 测试。"""

    async def test_get_by_id_found(self, db_session: AsyncSession):
        """存在的 ID 返回 ORM 实例。"""
        service = CategoryService(db_session)
        created = await service.create(CategoryCreate(name="存在的分类"))
        await db_session.commit()

        found = await service.get_by_id(created.id)

        assert found is not None
        assert found.id == created.id
        assert found.name == "存在的分类"

    async def test_get_by_id_not_found(self, db_session: AsyncSession):
        """不存在的 ID 返回 None。"""
        service = CategoryService(db_session)

        found = await service.get_by_id(9999)

        assert found is None


class TestCategoryServiceList:
    """CategoryService.list() / count() / list_paged() 测试。"""

    async def test_list_empty(self, db_session: AsyncSession):
        """无数据返回空列表。"""
        service = CategoryService(db_session)
        result = await service.list()
        assert result == []

    async def test_list_with_data(self, db_session: AsyncSession):
        """有数据时正确返回列表。"""
        service = CategoryService(db_session)
        for i in range(3):
            await service.create(CategoryCreate(name=f"分类{i}"))
        await db_session.commit()

        result = await service.list()
        assert len(result) == 3
        names = {c.name for c in result}
        assert names == {"分类0", "分类1", "分类2"}

    async def test_list_with_filters(self, db_session: AsyncSession):
        """按字段过滤。"""
        service = CategoryService(db_session)
        await service.create(CategoryCreate(name="电子"))
        await service.create(CategoryCreate(name="图书"))
        await db_session.commit()

        result = await service.list(name="电子")
        assert len(result) == 1
        assert result[0].name == "电子"

    async def test_count(self, db_session: AsyncSession):
        """count() 返回正确的数量。"""
        service = CategoryService(db_session)
        assert await service.count() == 0

        for i in range(5):
            await service.create(CategoryCreate(name=f"C{i}"))
        await db_session.commit()

        assert await service.count() == 5

    async def test_list_paged(self, db_session: AsyncSession):
        """list_paged() 返回 PageResult 且分页元数据正确。"""
        service = CategoryService(db_session)
        for i in range(5):
            await service.create(CategoryCreate(name=f"P{i}"))
        await db_session.commit()

        page1 = await service.list_paged(page=1, page_size=2)
        assert page1.total == 5
        assert page1.page == 1
        assert page1.page_size == 2
        assert len(page1.items) == 2

        page3 = await service.list_paged(page=3, page_size=2)
        assert len(page3.items) == 1  # 第 5 条

    async def test_list_paged_order_by_name(self, db_session: AsyncSession):
        """list_paged 按 name 升序。"""
        service = CategoryService(db_session)
        for name in ["Zebra", "Apple", "Mango"]:
            await service.create(CategoryCreate(name=name))
        await db_session.commit()

        result = await service.list_paged(order_by="name", ascending=True)
        names = [item.name for item in result.items]
        assert names == ["Apple", "Mango", "Zebra"]


class TestCategoryServiceUpdate:
    """CategoryService.update() 测试。"""

    async def test_update_partial(self, db_session: AsyncSession):
        """部分更新：只改 name。"""
        service = CategoryService(db_session)
        created = await service.create(
            CategoryCreate(name="旧名称", description="不变的描述")
        )
        await db_session.commit()

        updated = await service.update(created.id, CategoryUpdate(name="新名称"))
        await db_session.commit()

        assert updated.name == "新名称"
        assert updated.description == "不变的描述"

    async def test_update_not_found(self, db_session: AsyncSession):
        """更新不存在的记录抛 NOT_FOUND。"""
        service = CategoryService(db_session)

        with pytest.raises(DatabaseException) as exc_info:
            await service.update(9999, CategoryUpdate(name="不存在"))

        assert exc_info.value.error_code == ErrorCode.NOT_FOUND


class TestCategoryServiceDelete:
    """CategoryService.delete() 测试。"""

    async def test_delete_success(self, db_session: AsyncSession):
        """正常删除后 get_by_id 返回 None。"""
        service = CategoryService(db_session)
        created = await service.create(CategoryCreate(name="待删除"))
        await db_session.commit()

        await service.delete(created.id)
        await db_session.commit()

        assert await service.get_by_id(created.id) is None

    async def test_delete_not_found(self, db_session: AsyncSession):
        """删除不存在的记录抛 NOT_FOUND。"""
        service = CategoryService(db_session)

        with pytest.raises(DatabaseException) as exc_info:
            await service.delete(9999)

        assert exc_info.value.error_code == ErrorCode.NOT_FOUND


class TestCategoryServiceGetDetail:
    """CategoryService.get_detail() 测试。"""

    async def test_get_detail_with_products(self, db_session: AsyncSession):
        """get_detail 返回 CategoryResponseDetail，含关联 products。"""
        from web_service.model.product import Product

        service = CategoryService(db_session)
        cat = await service.create(CategoryCreate(name="图书"))

        # 直接用 SQL 插入 product 并建立中间表关联
        from sqlalchemy import insert
        from web_service.model.association import product_category

        product = Product(name="Python入门")
        db_session.add(product)
        await db_session.flush()

        await db_session.execute(
            insert(product_category).values(product_id=product.id, category_id=cat.id)
        )
        await db_session.commit()

        detail = await service.get_detail(cat.id)
        assert detail is not None
        assert detail.id == cat.id
        assert detail.name == "图书"
        assert len(detail.products) == 1
        assert detail.products[0].name == "Python入门"

    async def test_get_detail_not_found(self, db_session: AsyncSession):
        """不存在的 ID 返回 None。"""
        service = CategoryService(db_session)
        assert await service.get_detail(9999) is None


# ═══════════════════════════════════════════════════════════════════
# Category API 集成测试（通过 async_client 走真实 HTTP 到 subprocess server）
#
# 与 Service 层测试的区别：
# - 验证 API 路由 wiring / 依赖注入 / 响应序列化 / 统一响应格式
# - 验证异常处理中间件（NOT_FOUND / VALIDATION_ERROR）
# - 复用 integration/conftest.py 启动的测试服务器
# ═══════════════════════════════════════════════════════════════════


class TestCategoryAPICreate:
    """POST /api/categories 测试。"""

    async def test_create_category_via_api(self, async_client):
        """通过 API 创建分类，验证路由 wiring 和响应序列化。"""
        resp = await async_client.post(
            "/api/categories",
            json={"name": "API分类", "description": "API集成测试"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == "0"
        assert body["data"]["name"] == "API分类"
        assert body["data"]["description"] == "API集成测试"

    async def test_create_validation_error_via_api(self, async_client):
        """空 name 触发 422 校验错误。"""
        resp = await async_client.post(
            "/api/categories",
            json={"name": ""},
        )

        assert resp.status_code == 422


class TestCategoryAPIList:
    """GET /api/categories 测试。"""

    async def test_list_via_api(self, async_client):
        """空列表返回 PageResult 结构。"""
        resp = await async_client.get("/api/categories")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1


class TestCategoryAPIGet:
    """GET /api/categories/{id} 测试。"""

    async def test_get_not_found_via_api(self, async_client):
        """不存在的分类返回 404 + NOT_FOUND 错误码。"""
        resp = await async_client.get("/api/categories/9999")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == ErrorCode.NOT_FOUND.code

    async def test_get_detail_via_api(self, async_client):
        """存在的分类返回详情，含 products 列表。"""
        cat_resp = await async_client.post("/api/categories", json={"name": "详情分类"})
        cat_id = cat_resp.json()["data"]["id"]

        resp = await async_client.get(f"/api/categories/{cat_id}")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == cat_id
        assert data["name"] == "详情分类"
        assert data["products"] == []


class TestCategoryAPIUpdate:
    """PUT /api/categories/{id} 测试。"""

    async def test_update_via_api(self, async_client):
        """更新分类名称。"""
        cat_resp = await async_client.post("/api/categories", json={"name": "旧名称"})
        cat_id = cat_resp.json()["data"]["id"]

        resp = await async_client.put(
            f"/api/categories/{cat_id}", json={"name": "新名称"}
        )

        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "新名称"

    async def test_update_not_found_via_api(self, async_client):
        """更新不存在的分类返回 404。"""
        resp = await async_client.put("/api/categories/9999", json={"name": "不存在"})

        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code


class TestCategoryAPIDelete:
    """DELETE /api/categories/{id} 测试。"""

    async def test_delete_via_api(self, async_client):
        """删除分类返回 204。"""
        cat_resp = await async_client.post("/api/categories", json={"name": "待删除"})
        cat_id = cat_resp.json()["data"]["id"]

        resp = await async_client.delete(f"/api/categories/{cat_id}")
        assert resp.status_code == 204

    async def test_delete_not_found_via_api(self, async_client):
        """删除不存在的分类返回 404。"""
        resp = await async_client.delete("/api/categories/9999")
        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code
