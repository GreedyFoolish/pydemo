"""
Product API 集成测试。

通过 async_client 走真实 HTTP，
验证路由 wiring / 响应序列化 / 统一响应格式 / 异常处理（NOT_FOUND / DB_FK_CONFLICT）。
"""

from web_service.exception import ErrorCode


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
