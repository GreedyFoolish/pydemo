"""
Product API 端到端测试。

通过 HTTP 请求完整验证 Product 的 CRUD 链路，
包括统一响应格式、分页、关联分类、错误场景等。

运行方式：
    uv run --package web-service pytest test/e2e/test_product.py -v
"""

from httpx import AsyncClient


async def _create_category(async_client: AsyncClient, name: str) -> dict:
    """创建一个分类，返回统一响应体中的 data 字段。"""
    resp = await async_client.post(
        "/api/categories",
        json={"name": name},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "0"
    return body["data"]


# 创建产品（POST）
class TestCreateProduct:
    """POST /api/products 相关测试。"""

    async def test_create_product_with_category(self, async_client):
        """正常创建产品并关联一个分类，返回 201 + 统一响应格式。"""
        cat = await _create_category(async_client, "电子产品")

        resp = await async_client.post(
            "/api/products",
            json={
                "name": "iPhone 16",
                "description": "苹果最新款手机",
                "brand": "Apple",
                "category_ids": [cat["id"]],
            },
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
        assert data["name"] == "iPhone 16"
        assert data["brand"] == "Apple"
        assert data["description"] == "苹果最新款手机"
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_product_without_optional_fields(self, async_client):
        """只传必填字段 name，description/brand/category_ids 使用默认值。"""
        resp = await async_client.post(
            "/api/products",
            json={"name": "极简产品"},
        )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["id"] == 1
        assert data["name"] == "极简产品"
        # 可选字段默认值
        assert data["description"] == ""
        assert data["brand"] is None

    async def test_create_product_with_multiple_categories(self, async_client):
        """一个产品同时关联多个分类。"""
        cat1 = await _create_category(async_client, "电子产品")
        cat2 = await _create_category(async_client, "高端产品")

        resp = await async_client.post(
            "/api/products",
            json={
                "name": "MacBook Pro",
                "brand": "Apple",
                "category_ids": [cat1["id"], cat2["id"]],
            },
        )

        assert resp.status_code == 201

    async def test_create_product_nonexistent_category_fk_conflict(self, async_client):
        """关联不存在的分类 ID，应返回 409 外键冲突。"""
        resp = await async_client.post(
            "/api/products",
            json={
                "name": "幽灵产品",
                "category_ids": [9999],
            },
        )

        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "500102"  # DB_FK_CONFLICT

    async def test_create_product_empty_name_validation(self, async_client):
        """name 为空字符串，应返回 422 校验错误。"""
        resp = await async_client.post(
            "/api/products",
            json={"name": ""},
        )

        assert resp.status_code == 422

    async def test_create_product_missing_name_validation(self, async_client):
        """缺失必填字段 name，应返回 422 校验错误。"""
        resp = await async_client.post(
            "/api/products",
            json={"brand": "Apple"},
        )

        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 列表查询（GET 列表）
# ═══════════════════════════════════════════════════════════════════


class TestListProducts:
    """GET /api/products 相关测试。"""

    async def test_list_products_empty(self, async_client):
        """无数据时返回空列表，total=0。"""
        resp = await async_client.get("/api/products")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    async def test_list_products_with_data(self, async_client):
        """有数据时正确返回列表，total 与 items 长度匹配。"""
        for i in range(3):
            await async_client.post(
                "/api/products",
                json={"name": f"产品{i}"},
            )

        resp = await async_client.get("/api/products")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_list_products_pagination(self, async_client):
        """分页参数生效，page_size 限制单页数量。"""
        for i in range(5):
            await async_client.post(
                "/api/products",
                json={"name": f"产品{i}"},
            )

        # 第一页，2 条
        resp = await async_client.get(
            "/api/products", params={"page": 1, "page_size": 2}
        )
        data = resp.json()["data"]
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

        # 第二页，2 条（5 = 2 + 2 + 1）
        resp = await async_client.get(
            "/api/products", params={"page": 2, "page_size": 2}
        )
        data = resp.json()["data"]
        assert len(data["items"]) == 2
        assert data["page"] == 2

        # 第三页，剩下 1 条
        resp = await async_client.get(
            "/api/products", params={"page": 3, "page_size": 2}
        )
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["page"] == 3

    async def test_list_products_order_by(self, async_client):
        """按字段排序，ascending=True 升序 / False 降序。"""
        for name in ["Zebra", "Apple", "Mango"]:
            await async_client.post(
                "/api/products",
                json={"name": name},
            )

        # 升序
        resp = await async_client.get(
            "/api/products",
            params={"order_by": "name", "ascending": True},
        )
        items = resp.json()["data"]["items"]
        assert [i["name"] for i in items] == ["Apple", "Mango", "Zebra"]

        # 降序
        resp = await async_client.get(
            "/api/products",
            params={"order_by": "name", "ascending": False},
        )
        items = resp.json()["data"]["items"]
        assert [i["name"] for i in items] == ["Zebra", "Mango", "Apple"]

    async def test_list_products_page_out_of_range(self, async_client):
        """超出数据范围的页码，返回空 items 但 total 仍正确。"""
        await async_client.post("/api/products", json={"name": "唯一产品"})

        resp = await async_client.get(
            "/api/products",
            params={"page": 10, "page_size": 20},
        )
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"] == []


# ═══════════════════════════════════════════════════════════════════
# 获取详情（GET /{id}）
# ═══════════════════════════════════════════════════════════════════


class TestGetProduct:
    """GET /api/products/{id} 相关测试。"""

    async def test_get_product_detail(self, async_client):
        """获取存在的产品，返回详情（含关联分类）。"""
        cat = await _create_category(async_client, "图书")
        # 创建产品
        create_resp = await async_client.post(
            "/api/products",
            json={
                "name": "Python入门",
                "brand": "邮电",
                "category_ids": [cat["id"]],
            },
        )
        product_id = create_resp.json()["data"]["id"]

        # 获取详情
        resp = await async_client.get(f"/api/products/{product_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["id"] == product_id
        assert data["name"] == "Python入门"
        assert data["brand"] == "邮电"
        # 分类关联正确
        assert len(data["categories"]) == 1
        assert data["categories"][0]["id"] == cat["id"]
        assert data["categories"][0]["name"] == "图书"
        # SKU 列表为空（还没创建 SKU）
        assert data["skus"] == []

    async def test_get_product_not_found(self, async_client):
        """获取不存在的产品 ID，应返回 404。"""
        resp = await async_client.get("/api/products/9999")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "404001"  # NOT_FOUND


# ═══════════════════════════════════════════════════════════════════
# 更新产品（PUT）
# ═══════════════════════════════════════════════════════════════════


class TestUpdateProduct:
    """PUT /api/products/{id} 相关测试。"""

    async def test_update_product_partial(self, async_client):
        """部分更新：只改 name，其他字段保持不变。"""
        cat = await _create_category(async_client, "分类A")
        create_resp = await async_client.post(
            "/api/products",
            json={
                "name": "旧名称",
                "description": "不变的描述",
                "brand": "不变的品牌",
                "category_ids": [cat["id"]],
            },
        )
        product_id = create_resp.json()["data"]["id"]

        # 只更新 name
        resp = await async_client.put(
            f"/api/products/{product_id}",
            json={"name": "新名称"},
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "新名称"
        assert data["description"] == "不变的描述"
        assert data["brand"] == "不变的品牌"

    async def test_update_product_category_ids(self, async_client):
        """更新 category_ids 应完全替换旧的关联。"""
        cat_a = await _create_category(async_client, "分类A")
        cat_b = await _create_category(async_client, "分类B")
        cat_c = await _create_category(async_client, "分类C")

        create_resp = await async_client.post(
            "/api/products",
            json={
                "name": "产品",
                "category_ids": [cat_a["id"], cat_b["id"]],
            },
        )
        product_id = create_resp.json()["data"]["id"]

        # 详情确认初始关联
        detail_resp = await async_client.get(f"/api/products/{product_id}")
        detail_data = detail_resp.json()["data"]
        cat_names = {c["name"] for c in detail_data["categories"]}
        assert cat_names == {"分类A", "分类B"}

        # 更新关联：替换为 [分类C]
        await async_client.put(
            f"/api/products/{product_id}",
            json={"category_ids": [cat_c["id"]]},
        )

        # 再次确认：只剩分类C
        detail_resp = await async_client.get(f"/api/products/{product_id}")
        detail_data = detail_resp.json()["data"]
        cat_names = {c["name"] for c in detail_data["categories"]}
        assert cat_names == {"分类C"}

    async def test_update_product_not_found(self, async_client):
        """更新不存在的产品 ID，应返回 404。"""
        resp = await async_client.put(
            "/api/products/9999",
            json={"name": "不存在"},
        )

        assert resp.status_code == 404
        assert resp.json()["code"] == "404001"

    async def test_update_product_to_nonexistent_category(self, async_client):
        """更新时关联不存在的分类，应返回 409 外键冲突。"""
        create_resp = await async_client.post(
            "/api/products",
            json={"name": "待更新产品"},
        )
        product_id = create_resp.json()["data"]["id"]

        resp = await async_client.put(
            f"/api/products/{product_id}",
            json={"category_ids": [9999]},
        )

        assert resp.status_code == 409
        assert resp.json()["code"] == "500102"


# ═══════════════════════════════════════════════════════════════════
# 删除产品（DELETE）
# ═══════════════════════════════════════════════════════════════════


class TestDeleteProduct:
    """DELETE /api/products/{id} 相关测试。"""

    async def test_delete_product_success(self, async_client):
        """删除存在的产品，返回 204 No Content。"""
        create_resp = await async_client.post(
            "/api/products",
            json={"name": "待删除产品"},
        )
        product_id = create_resp.json()["data"]["id"]

        resp = await async_client.delete(f"/api/products/{product_id}")

        # 204 No Content：HTTP 规范不允许有 body，中间件已跳过包装，
        # 所以 httpx 返回的是原始响应，没有统一响应格式
        assert resp.status_code == 204

        # 再次查询应返回 404
        resp = await async_client.get(f"/api/products/{product_id}")
        assert resp.status_code == 404

    async def test_delete_product_not_found(self, async_client):
        """删除不存在的产品 ID，应返回 404。"""
        resp = await async_client.delete("/api/products/9999")

        assert resp.status_code == 404
        assert resp.json()["code"] == "404001"


# 多用例间隔离验证
class TestIsolationBetweenCases:
    """验证 cleanup_db autouse fixture 确实在每个用例后清空了数据。"""

    async def test_case_a_creates_data(self, async_client):
        """用例 A 创建一个产品。"""
        await async_client.post("/api/products", json={"name": "A创建的"})
        resp = await async_client.get("/api/products")
        assert resp.json()["data"]["total"] == 1

    async def test_case_b_starts_fresh(self, async_client):
        """用例 B 开始时数据库应是空的（用例 A 的数据已被 TRUNCATE）。"""
        resp = await async_client.get("/api/products")
        assert (
            resp.json()["data"]["total"] == 0
        ), "用例 A 创建的数据应已被 cleanup fixture TRUNCATE"
