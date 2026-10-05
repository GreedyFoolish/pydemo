"""
Category API 端到端测试。

通过 HTTP 请求完整验证 Category 的 CRUD 链路，
包括统一响应格式、分页、关联产品、错误场景等。

运行方式：
    uv run --package web-service pytest test/e2e/test_category.py -v
"""

import pytest

# ═══════════════════════════════════════════════════════════════════
# 创建分类（POST）
# ═══════════════════════════════════════════════════════════════════


class TestCreateCategory:
    """POST /api/categories 相关测试。"""

    async def test_create_category_with_name_only(self, async_client):
        """只传必填字段 name，description 使用默认值。"""
        resp = await async_client.post(
            "/api/categories",
            json={"name": "电子产品"},
        )

        assert resp.status_code == 201
        body = resp.json()
        # 统一响应格式校验
        assert body["code"] == "0"
        assert body["message"] == "success"
        assert "request_id" in body
        data = body["data"]
        # 业务字段校验
        assert data["id"] == 1
        assert data["name"] == "电子产品"
        assert data["description"] == ""

    async def test_create_category_with_description(self, async_client):
        """同时传 name 和 description。"""
        resp = await async_client.post(
            "/api/categories",
            json={
                "name": "图书",
                "description": "各类书籍和阅读材料",
            },
        )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "图书"
        assert data["description"] == "各类书籍和阅读材料"

    async def test_create_category_empty_name_validation(self, async_client):
        """name 为空字符串，应返回 422 校验错误。"""
        resp = await async_client.post(
            "/api/categories",
            json={"name": ""},
        )

        assert resp.status_code == 422

    async def test_create_category_missing_name_validation(self, async_client):
        """缺失必填字段 name，应返回 422 校验错误。"""
        resp = await async_client.post(
            "/api/categories",
            json={"description": "没有名称"},
        )

        assert resp.status_code == 422

    async def test_create_category_name_too_long(self, async_client):
        """name 超过 50 字符上限，应返回 422 校验错误。"""
        resp = await async_client.post(
            "/api/categories",
            json={"name": "A" * 51},
        )

        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 列表查询（GET 列表）
# ═══════════════════════════════════════════════════════════════════


class TestListCategories:
    """GET /api/categories 相关测试。"""

    async def test_list_categories_empty(self, async_client):
        """无数据时返回空列表，total=0。"""
        resp = await async_client.get("/api/categories")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    async def test_list_categories_with_data(self, async_client):
        """有数据时正确返回列表，total 与 items 长度匹配。"""
        for i in range(3):
            await async_client.post(
                "/api/categories",
                json={"name": f"分类{i}"},
            )

        resp = await async_client.get("/api/categories")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_list_categories_pagination(self, async_client):
        """分页参数生效，page_size 限制单页数量。"""
        for i in range(5):
            await async_client.post(
                "/api/categories",
                json={"name": f"分类{i}"},
            )

        # 第一页，2 条
        resp = await async_client.get(
            "/api/categories", params={"page": 1, "page_size": 2}
        )
        data = resp.json()["data"]
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

        # 第二页，2 条
        resp = await async_client.get(
            "/api/categories", params={"page": 2, "page_size": 2}
        )
        data = resp.json()["data"]
        assert len(data["items"]) == 2
        assert data["page"] == 2

        # 第三页，剩下 1 条
        resp = await async_client.get(
            "/api/categories", params={"page": 3, "page_size": 2}
        )
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["page"] == 3

    async def test_list_categories_order_by(self, async_client):
        """按字段排序，ascending=True 升序 / False 降序。"""
        for name in ["Zebra", "Apple", "Mango"]:
            await async_client.post(
                "/api/categories",
                json={"name": name},
            )

        # 升序
        resp = await async_client.get(
            "/api/categories",
            params={"order_by": "name", "ascending": True},
        )
        items = resp.json()["data"]["items"]
        assert [i["name"] for i in items] == ["Apple", "Mango", "Zebra"]

        # 降序
        resp = await async_client.get(
            "/api/categories",
            params={"order_by": "name", "ascending": False},
        )
        items = resp.json()["data"]["items"]
        assert [i["name"] for i in items] == ["Zebra", "Mango", "Apple"]

    async def test_list_categories_page_out_of_range(self, async_client):
        """超出数据范围的页码，返回空 items 但 total 仍正确。"""
        await async_client.post("/api/categories", json={"name": "唯一分类"})

        resp = await async_client.get(
            "/api/categories",
            params={"page": 10, "page_size": 20},
        )
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"] == []


# ═══════════════════════════════════════════════════════════════════
# 获取详情（GET /{id}）
# ═══════════════════════════════════════════════════════════════════


class TestGetCategory:
    """GET /api/categories/{id} 相关测试。"""

    async def test_get_category_detail(self, async_client):
        """获取存在的分类，返回详情（含关联产品列表）。"""
        # 先创建分类
        create_resp = await async_client.post(
            "/api/categories",
            json={
                "name": "图书",
                "description": "各类书籍",
            },
        )
        category_id = create_resp.json()["data"]["id"]

        # 创建一个产品关联到这个分类
        await async_client.post(
            "/api/products",
            json={
                "name": "Python入门",
                "category_ids": [category_id],
            },
        )

        # 获取详情
        resp = await async_client.get(f"/api/categories/{category_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["id"] == category_id
        assert data["name"] == "图书"
        assert data["description"] == "各类书籍"
        # 关联产品正确
        assert len(data["products"]) == 1
        assert data["products"][0]["name"] == "Python入门"

    async def test_get_category_without_products(self, async_client):
        """获取没有关联产品的分类，products 应为空列表。"""
        create_resp = await async_client.post(
            "/api/categories",
            json={"name": "空分类"},
        )
        category_id = create_resp.json()["data"]["id"]

        resp = await async_client.get(f"/api/categories/{category_id}")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["products"] == []

    async def test_get_category_not_found(self, async_client):
        """获取不存在的分类 ID，应返回 404。"""
        resp = await async_client.get("/api/categories/9999")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "404001"  # NOT_FOUND


# ═══════════════════════════════════════════════════════════════════
# 更新分类（PUT）
# ═══════════════════════════════════════════════════════════════════


class TestUpdateCategory:
    """PUT /api/categories/{id} 相关测试。"""

    async def test_update_category_partial(self, async_client):
        """部分更新：只改 name，其他字段保持不变。"""
        create_resp = await async_client.post(
            "/api/categories",
            json={
                "name": "旧名称",
                "description": "不变的描述",
            },
        )
        category_id = create_resp.json()["data"]["id"]

        # 只更新 name
        resp = await async_client.put(
            f"/api/categories/{category_id}",
            json={"name": "新名称"},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "新名称"
        assert data["description"] == "不变的描述"

    async def test_update_category_all_fields(self, async_client):
        """更新所有字段。"""
        create_resp = await async_client.post(
            "/api/categories",
            json={
                "name": "旧名称",
                "description": "旧描述",
            },
        )
        category_id = create_resp.json()["data"]["id"]

        resp = await async_client.put(
            f"/api/categories/{category_id}",
            json={
                "name": "全新名称",
                "description": "全新描述",
            },
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "全新名称"
        assert data["description"] == "全新描述"

    async def test_update_category_not_found(self, async_client):
        """更新不存在的分类 ID，应返回 404。"""
        resp = await async_client.put(
            "/api/categories/9999",
            json={"name": "不存在"},
        )

        assert resp.status_code == 404
        assert resp.json()["code"] == "404001"

    async def test_update_category_empty_name_validation(self, async_client):
        """更新时 name 为空字符串，应返回 422 校验错误。"""
        create_resp = await async_client.post(
            "/api/categories",
            json={"name": "有效名称"},
        )
        category_id = create_resp.json()["data"]["id"]

        resp = await async_client.put(
            f"/api/categories/{category_id}",
            json={"name": ""},
        )

        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 删除分类（DELETE）
# ═══════════════════════════════════════════════════════════════════


class TestDeleteCategory:
    """DELETE /api/categories/{id} 相关测试。"""

    async def test_delete_category_success(self, async_client):
        """删除存在的分类，返回 204 No Content。"""
        create_resp = await async_client.post(
            "/api/categories",
            json={"name": "待删除分类"},
        )
        category_id = create_resp.json()["data"]["id"]

        resp = await async_client.delete(f"/api/categories/{category_id}")

        # 204 No Content：HTTP 规范不允许有 body，中间件已跳过包装
        assert resp.status_code == 204

        # 再次查询应返回 404
        resp = await async_client.get(f"/api/categories/{category_id}")
        assert resp.status_code == 404

    async def test_delete_category_with_products(self, async_client):
        """删除被产品关联的分类，中间表记录应自动清理。"""
        # 创建分类和产品关联
        cat_resp = await async_client.post(
            "/api/categories",
            json={"name": "关联分类"},
        )
        category_id = cat_resp.json()["data"]["id"]

        prod_resp = await async_client.post(
            "/api/products",
            json={
                "name": "关联产品",
                "category_ids": [category_id],
            },
        )
        product_id = prod_resp.json()["data"]["id"]

        # 删除分类
        resp = await async_client.delete(f"/api/categories/{category_id}")
        assert resp.status_code == 204

        # 产品应仍然存在（中间表记录被清理，但产品本身不受影响）
        resp = await async_client.get(f"/api/products/{product_id}")
        assert resp.status_code == 200
        # 产品不再有这个分类关联
        data = resp.json()["data"]
        cat_ids = [c["id"] for c in data["categories"]]
        assert category_id not in cat_ids

    async def test_delete_category_not_found(self, async_client):
        """删除不存在的分类 ID，应返回 404。"""
        resp = await async_client.delete("/api/categories/9999")

        assert resp.status_code == 404
        assert resp.json()["code"] == "404001"


# ═══════════════════════════════════════════════════════════════════
# 多用例间隔离验证
# ═══════════════════════════════════════════════════════════════════


class TestCategoryIsolation:
    """验证 cleanup_db autouse fixture 确实在每个用例后清空了数据。"""

    async def test_case_a_creates_data(self, async_client):
        """用例 A 创建一个分类。"""
        await async_client.post("/api/categories", json={"name": "A创建的"})
        resp = await async_client.get("/api/categories")
        assert resp.json()["data"]["total"] == 1

    async def test_case_b_starts_fresh(self, async_client):
        """用例 B 开始时数据库应是空的（用例 A 的数据已被 TRUNCATE）。"""
        resp = await async_client.get("/api/categories")
        assert (
            resp.json()["data"]["total"] == 0
        ), "用例 A 创建的数据应已被 cleanup fixture TRUNCATE"
