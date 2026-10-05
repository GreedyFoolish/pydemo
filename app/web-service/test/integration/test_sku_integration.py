"""
SKU Service + API 集成测试。

覆盖范围：
- SkuService 直接测试
  - create（重点：_require_exists 外键校验 product_id）
  - get_detail（含 selectinload 预加载 product）
  - 继承 BaseService 的 get_by_id / list / list_paged / update / delete
  - IntegrityError → DatabaseException 转换（sku_code 唯一冲突）
  - 级联删除验证
- SkuAPI 通过 ASGI transport 测试
  - 路由 wiring / 响应序列化
  - 外键冲突（不存在的 product_id → 404 NOT_FOUND）
  - 唯一约束冲突（重复 sku_code → 409 DB_UNIQUE_CONFLICT）
  - 校验错误 / 统一响应格式 / 异常处理
"""

import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.exception import DatabaseException, ErrorCode
from web_service.model.product import Product
from web_service.model.sku import Sku
from web_service.schema.product import ProductCreate
from web_service.schema.sku import SkuCreate, SkuUpdate
from web_service.service.product import ProductService
from web_service.service.sku import SkuService

# ═══════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════


async def _create_product(db_session: AsyncSession, name: str) -> int:
    """在测试 session 中创建一个产品，返回其 ID。"""
    service = ProductService(db_session)
    instance = await service.create(ProductCreate(name=name))
    await db_session.commit()
    return instance.id


async def _make_sku_create(product_id: int, sku_code: str = "SKU-TEST") -> SkuCreate:
    """构造一个合法的 SkuCreate DTO。"""
    return SkuCreate(
        product_id=product_id,
        sku_code=sku_code,
        price=Decimal("10.00"),
        stock=0,
        attrs={"颜色": "黑色"},
        image_url="https://example.com/img.jpg",
    )


# ═══════════════════════════════════════════════════════════════════
# SkuService 集成测试
# ═══════════════════════════════════════════════════════════════════


class TestSkuServiceCreate:
    """SkuService.create() 测试（重点：外键校验）。"""

    async def test_create_sku_success(self, db_session: AsyncSession):
        """正常创建 SKU。"""
        product_id = await _create_product(db_session, "测试产品")

        service = SkuService(db_session)
        schema = await _make_sku_create(product_id, "SKU-SUCCESS")

        instance = await service.create(schema)
        await db_session.commit()

        assert isinstance(instance, Sku)
        assert instance.id is not None
        assert instance.product_id == product_id
        assert instance.sku_code == "SKU-SUCCESS"
        assert instance.price == Decimal("10.00")

    async def test_create_sku_nonexistent_product_not_found(
        self, db_session: AsyncSession
    ):
        """product_id 不存在 → SkuService.create 先做 _require_exists 预校验，返回 NOT_FOUND(404)。"""
        service = SkuService(db_session)
        schema = await _make_sku_create(product_id=9999, sku_code="SKU-NO-PROD")

        with pytest.raises(DatabaseException) as exc_info:
            await service.create(schema)

        assert exc_info.value.error_code == ErrorCode.NOT_FOUND

    async def test_create_sku_duplicate_code(self, db_session: AsyncSession):
        """sku_code 重复 → DB_UNIQUE_CONFLICT(409)。"""
        product_id = await _create_product(db_session, "重复产品")

        service = SkuService(db_session)
        schema = await _make_sku_create(product_id, "SKU-DUP")

        await service.create(schema)
        await db_session.commit()

        # 再次使用相同 sku_code
        with pytest.raises(DatabaseException) as exc_info:
            await service.create(schema)

        assert exc_info.value.error_code == ErrorCode.DB_UNIQUE_CONFLICT


class TestSkuServiceGetById:
    """SkuService.get_by_id() 测试。"""

    async def test_get_by_id_found(self, db_session: AsyncSession):
        """存在的 ID 返回 ORM 实例。"""
        product_id = await _create_product(db_session, "查询产品")
        service = SkuService(db_session)
        created = await service.create(await _make_sku_create(product_id, "SKU-GET"))
        await db_session.commit()

        found = await service.get_by_id(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.sku_code == "SKU-GET"

    async def test_get_by_id_not_found(self, db_session: AsyncSession):
        """不存在的 ID 返回 None。"""
        service = SkuService(db_session)
        assert await service.get_by_id(9999) is None


class TestSkuServiceUpdate:
    """SkuService.update() 测试。"""

    async def test_update_partial(self, db_session: AsyncSession):
        """部分更新 price 和 stock。"""
        product_id = await _create_product(db_session, "更新产品")
        service = SkuService(db_session)
        created = await service.create(await _make_sku_create(product_id, "SKU-UPD"))
        await db_session.commit()

        updated = await service.update(
            created.id,
            SkuUpdate(price=Decimal("99.99"), stock=50),
        )
        await db_session.commit()

        assert updated.price == Decimal("99.99")
        assert updated.stock == 50
        # 未更新字段保持不变
        assert updated.sku_code == "SKU-UPD"

    async def test_update_duplicate_code(self, db_session: AsyncSession):
        """更新 sku_code 为已存在的编码 → DB_UNIQUE_CONFLICT。"""
        product_id = await _create_product(db_session, "冲突产品")
        service = SkuService(db_session)

        sku_a = await service.create(await _make_sku_create(product_id, "SKU-A"))
        sku_b = await service.create(await _make_sku_create(product_id, "SKU-B"))
        await db_session.commit()

        with pytest.raises(DatabaseException) as exc_info:
            await service.update(sku_b.id, SkuUpdate(sku_code="SKU-A"))

        assert exc_info.value.error_code == ErrorCode.DB_UNIQUE_CONFLICT

    async def test_update_not_found(self, db_session: AsyncSession):
        """更新不存在的 SKU → NOT_FOUND。"""
        service = SkuService(db_session)
        with pytest.raises(DatabaseException) as exc_info:
            await service.update(9999, SkuUpdate(price=Decimal("10.00")))
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND


class TestSkuServiceDelete:
    """SkuService.delete() 测试。"""

    async def test_delete_success(self, db_session: AsyncSession):
        """删除后 get_by_id 返回 None。"""
        product_id = await _create_product(db_session, "删除产品")
        service = SkuService(db_session)
        created = await service.create(await _make_sku_create(product_id, "SKU-DEL"))
        await db_session.commit()

        await service.delete(created.id)
        await db_session.commit()

        assert await service.get_by_id(created.id) is None

    async def test_delete_not_found(self, db_session: AsyncSession):
        """删除不存在的 SKU → NOT_FOUND。"""
        service = SkuService(db_session)
        with pytest.raises(DatabaseException) as exc_info:
            await service.delete(9999)
        assert exc_info.value.error_code == ErrorCode.NOT_FOUND


class TestSkuServiceDetail:
    """SkuService.get_detail() 测试。"""

    async def test_get_detail_with_product(self, db_session: AsyncSession):
        """get_detail 预加载 product 关联。"""
        product_id = await _create_product(db_session, "详情产品")
        service = SkuService(db_session)
        created = await service.create(await _make_sku_create(product_id, "SKU-DETAIL"))
        await db_session.commit()

        detail = await service.get_detail(created.id)
        assert detail is not None
        assert detail.id == created.id
        assert detail.sku_code == "SKU-DETAIL"
        # 预加载的 product 关联
        assert detail.product is not None
        assert detail.product.id == product_id
        assert detail.product.name == "详情产品"

    async def test_get_detail_not_found(self, db_session: AsyncSession):
        """不存在的 SKU 返回 None。"""
        service = SkuService(db_session)
        assert await service.get_detail(9999) is None


class TestSkuServiceList:
    """SkuService.list_paged() 测试。"""

    async def test_list_paged(self, db_session: AsyncSession):
        """分页查询 SKU。"""
        product_id = await _create_product(db_session, "分页产品")
        service = SkuService(db_session)

        for i in range(3):
            await service.create(await _make_sku_create(product_id, f"SKU-LIST-{i}"))
        await db_session.commit()

        page = await service.list_paged(page=1, page_size=2)
        assert page.total == 3
        assert page.page == 1
        assert page.page_size == 2
        assert len(page.items) == 2


class TestSkuServiceCascadeDelete:
    """级联删除验证（Product 删除后 SKU 被 CASCADE 删除）。"""

    async def test_product_delete_cascades_skus(self, db_session: AsyncSession):
        """删除产品后，其 SKU 被数据库 ON DELETE CASCADE 自动删除。"""
        product_id = await _create_product(db_session, "级联产品")

        sku_service = SkuService(db_session)
        for i in range(3):
            await sku_service.create(
                await _make_sku_create(product_id, f"SKU-CASCADE-{i}")
            )
        await db_session.commit()

        # 确认 3 个 SKU 存在
        assert await sku_service.count() == 3

        # 删除产品（注意 ProductService.delete 使用 passive_deletes=True）
        product_service = ProductService(db_session)
        await product_service.delete(product_id)
        await db_session.commit()

        # SKU 应该被 CASCADE 删除
        assert await sku_service.count() == 0


# ═══════════════════════════════════════════════════════════════════
# SKU API 集成测试（通过 async_client 走真实 HTTP）
#
# 与 Service 层测试的区别：
# - 验证 API 路由 wiring / 依赖注入 / 响应序列化 / 统一响应格式
# - 验证异常处理中间件（NOT_FOUND / DB_UNIQUE_CONFLICT / VALIDATION_ERROR）
# ═══════════════════════════════════════════════════════════════════


async def _api_create_product(async_client, name: str) -> int:
    """通过 API 创建产品，返回其 ID。"""
    resp = await async_client.post("/api/products", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["data"]["id"]


class TestSkuAPICreate:
    """POST /api/skus 测试。"""

    async def test_create_sku_via_api(self, async_client):
        """正常创建 SKU。"""
        product_id = await _api_create_product(async_client, "API产品")

        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product_id,
                "sku_code": "SKU-API-1",
                "price": "199.99",
                "stock": 50,
                "attrs": {"颜色": "白色"},
                "image_url": "https://example.com/api.jpg",
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["code"] == "0"
        assert body["data"]["sku_code"] == "SKU-API-1"
        assert float(body["data"]["price"]) == 199.99

    async def test_create_sku_nonexistent_product_via_api(self, async_client):
        """不存在的 product_id → 404 NOT_FOUND（SkuService.create 预校验）。"""
        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": 9999,
                "sku_code": "SKU-NO-PROD",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )

        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code

    async def test_create_sku_duplicate_code_via_api(self, async_client):
        """重复 sku_code → 409 DB_UNIQUE_CONFLICT。"""
        product_id = await _api_create_product(async_client, "重复产品")

        await async_client.post(
            "/api/skus",
            json={
                "product_id": product_id,
                "sku_code": "SKU-DUP",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/a.jpg",
            },
        )

        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product_id,
                "sku_code": "SKU-DUP",
                "price": "20.00",
                "attrs": {},
                "image_url": "https://example.com/b.jpg",
            },
        )

        assert resp.status_code == 409
        assert resp.json()["code"] == ErrorCode.DB_UNIQUE_CONFLICT.code

    async def test_create_sku_validation_error_via_api(self, async_client):
        """price 为负数 → 422 校验错误。"""
        product_id = await _api_create_product(async_client, "校验产品")

        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product_id,
                "sku_code": "SKU-NEG",
                "price": "-10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )

        assert resp.status_code == 422


class TestSkuAPIList:
    """GET /api/skus 测试。"""

    async def test_list_empty_via_api(self, async_client):
        """空列表返回正确结构。"""
        resp = await async_client.get("/api/skus")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert body["data"]["items"] == []
        assert body["data"]["total"] == 0


class TestSkuAPIGet:
    """GET /api/skus/{id} 测试。"""

    async def test_get_not_found_via_api(self, async_client):
        """不存在的 SKU → 404。"""
        resp = await async_client.get("/api/skus/9999")
        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code


class TestSkuAPIUpdate:
    """PUT /api/skus/{id} 测试。"""

    async def test_update_via_api(self, async_client):
        """更新 SKU price。"""
        product_id = await _api_create_product(async_client, "更新产品")

        create_resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product_id,
                "sku_code": "SKU-UPD",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )
        sku_id = create_resp.json()["data"]["id"]

        resp = await async_client.put(f"/api/skus/{sku_id}", json={"price": "88.88"})

        assert resp.status_code == 200
        assert float(resp.json()["data"]["price"]) == 88.88

    async def test_update_not_found_via_api(self, async_client):
        """更新不存在的 SKU → 404。"""
        resp = await async_client.put("/api/skus/9999", json={"price": "10.00"})
        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code


class TestSkuAPIDelete:
    """DELETE /api/skus/{id} 测试。"""

    async def test_delete_via_api(self, async_client):
        """删除 SKU 返回 204。"""
        product_id = await _api_create_product(async_client, "删除产品")

        create_resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product_id,
                "sku_code": "SKU-DEL",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )
        sku_id = create_resp.json()["data"]["id"]

        resp = await async_client.delete(f"/api/skus/{sku_id}")
        assert resp.status_code == 204

    async def test_delete_not_found_via_api(self, async_client):
        """删除不存在的 SKU → 404。"""
        resp = await async_client.delete("/api/skus/9999")
        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code
