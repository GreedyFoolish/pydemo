"""
Category API 集成测试。

通过 async_client 走真实 HTTP，
验证路由 wiring / 响应序列化 / 统一响应格式 / 异常处理。
"""

from web_service.exception import ErrorCode


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
