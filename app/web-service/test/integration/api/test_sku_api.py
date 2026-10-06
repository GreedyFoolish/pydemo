"""
SKU API 集成测试。

通过 async_client 走真实 HTTP，
验证路由 wiring / 响应序列化 / 统一响应格式 / 异常处理。
"""

from web_service.exception import ErrorCode


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
