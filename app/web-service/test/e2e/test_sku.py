"""
SKU API 端到端测试。

通过 HTTP 请求完整验证 SKU 的 CRUD 链路，
包括统一响应格式、分页、外键 product_id 约束、
sku_code 唯一约束、级联删除、错误场景等。

运行方式：
    uv run --package web-service pytest test/e2e/test_sku.py -v
"""

import pytest


async def _create_product(async_client, name: str) -> dict:
    """创建一个产品，返回统一响应体中的 data 字段。"""
    resp = await async_client.post(
        "/api/products",
        json={"name": name},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["code"] == "0"
    return body["data"]


# ═══════════════════════════════════════════════════════════════════
# 创建 SKU（POST）
# ═══════════════════════════════════════════════════════════════════


class TestCreateSku:
    """POST /api/skus 相关测试。"""

    async def test_create_sku_success(self, async_client):
        """正常创建 SKU，传全部必填字段。"""
        product = await _create_product(async_client, "测试产品")

        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-001",
                "price": "99.99",
                "stock": 100,
                "attrs": {"颜色": "黑色", "尺寸": "L"},
                "image_url": "https://example.com/img.jpg",
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
        assert data["product_id"] == product["id"]
        assert data["sku_code"] == "SKU-001"
        assert float(data["price"]) == 99.99
        assert data["stock"] == 100
        assert data["attrs"] == {"颜色": "黑色", "尺寸": "L"}
        assert data["image_url"] == "https://example.com/img.jpg"

    async def test_create_sku_with_defaults(self, async_client):
        """只传必填字段，stock 使用默认值 0。"""
        product = await _create_product(async_client, "默认库存产品")

        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-DEFAULT",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/default.jpg",
            },
        )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["stock"] == 0  # 默认值
        assert data["attrs"] == {}

    async def test_create_sku_nonexistent_product_not_found(self, async_client):
        """关联不存在的 product_id，SkuService 先校验存在性应返回 404。

        注意：SkuService.create 使用 _require_exists 预校验 product_id，
        不存在时直接抛 NOT_FOUND（404），而不是等待数据库 FK 约束触发 DB_FK_CONFLICT（409）。
        """
        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": 9999,
                "sku_code": "SKU-NO-PRODUCT",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "404001"  # NOT_FOUND

    async def test_create_sku_negative_price_validation(self, async_client):
        """price 为负数，应返回 422 校验错误。"""
        product = await _create_product(async_client, "价格测试产品")

        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-NEG-PRICE",
                "price": "-10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )

        assert resp.status_code == 422

    async def test_create_sku_zero_price_validation(self, async_client):
        """price 为 0，应返回 422 校验错误（gt=0）。"""
        product = await _create_product(async_client, "零价产品")

        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-ZERO",
                "price": "0",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )

        assert resp.status_code == 422

    async def test_create_sku_negative_stock_validation(self, async_client):
        """stock 为负数，应返回 422 校验错误。"""
        product = await _create_product(async_client, "库存测试产品")

        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-NEG-STOCK",
                "price": "10.00",
                "stock": -1,
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )

        assert resp.status_code == 422

    async def test_create_sku_missing_required_fields(self, async_client):
        """缺失必填字段 sku_code，应返回 422 校验错误。"""
        product = await _create_product(async_client, "缺字段产品")

        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )

        assert resp.status_code == 422

    async def test_create_sku_duplicate_code(self, async_client):
        """sku_code 重复，应返回 409 唯一约束冲突。"""
        product = await _create_product(async_client, "重复编码产品")

        # 创建第一个 SKU
        await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-DUP",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/dup1.jpg",
            },
        )

        # 创建第二个使用相同 sku_code
        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-DUP",
                "price": "20.00",
                "attrs": {},
                "image_url": "https://example.com/dup2.jpg",
            },
        )

        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "500101"  # DB_UNIQUE_CONFLICT

    async def test_create_sku_zero_product_id(self, async_client):
        """product_id 为 0，应返回 422 校验错误（gt=0）。"""
        resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": 0,
                "sku_code": "SKU-ZERO-PID",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )

        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════
# 列表查询（GET 列表）
# ═══════════════════════════════════════════════════════════════════


class TestListSkus:
    """GET /api/skus 相关测试。"""

    async def test_list_skus_empty(self, async_client):
        """无数据时返回空列表，total=0。"""
        resp = await async_client.get("/api/skus")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    async def test_list_skus_with_data(self, async_client):
        """有数据时正确返回列表，total 与 items 长度匹配。"""
        product = await _create_product(async_client, "多SKU产品")

        for i in range(3):
            await async_client.post(
                "/api/skus",
                json={
                    "product_id": product["id"],
                    "sku_code": f"SKU-LIST-{i}",
                    "price": f"{10 + i}.00",
                    "attrs": {},
                    "image_url": f"https://example.com/{i}.jpg",
                },
            )

        resp = await async_client.get("/api/skus")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_list_skus_pagination(self, async_client):
        """分页参数生效，page_size 限制单页数量。"""
        product = await _create_product(async_client, "分页产品")

        for i in range(5):
            await async_client.post(
                "/api/skus",
                json={
                    "product_id": product["id"],
                    "sku_code": f"SKU-PAGE-{i}",
                    "price": "10.00",
                    "attrs": {},
                    "image_url": "https://example.com/img.jpg",
                },
            )

        # 第一页，2 条
        resp = await async_client.get("/api/skus", params={"page": 1, "page_size": 2})
        data = resp.json()["data"]
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2

        # 第二页，2 条
        resp = await async_client.get("/api/skus", params={"page": 2, "page_size": 2})
        data = resp.json()["data"]
        assert len(data["items"]) == 2
        assert data["page"] == 2

        # 第三页，剩下 1 条
        resp = await async_client.get("/api/skus", params={"page": 3, "page_size": 2})
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["page"] == 3

    async def test_list_skus_order_by(self, async_client):
        """按字段排序，ascending=True 升序 / False 降序。"""
        product = await _create_product(async_client, "排序产品")

        for code in ["SKU-Z", "SKU-A", "SKU-M"]:
            await async_client.post(
                "/api/skus",
                json={
                    "product_id": product["id"],
                    "sku_code": code,
                    "price": "10.00",
                    "attrs": {},
                    "image_url": "https://example.com/img.jpg",
                },
            )

        # 升序
        resp = await async_client.get(
            "/api/skus",
            params={"order_by": "sku_code", "ascending": True},
        )
        items = resp.json()["data"]["items"]
        assert [i["sku_code"] for i in items] == ["SKU-A", "SKU-M", "SKU-Z"]

        # 降序
        resp = await async_client.get(
            "/api/skus",
            params={"order_by": "sku_code", "ascending": False},
        )
        items = resp.json()["data"]["items"]
        assert [i["sku_code"] for i in items] == ["SKU-Z", "SKU-M", "SKU-A"]

    async def test_list_skus_page_out_of_range(self, async_client):
        """超出数据范围的页码，返回空 items 但 total 仍正确。"""
        product = await _create_product(async_client, "超页产品")
        await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-ONLY",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )

        resp = await async_client.get(
            "/api/skus",
            params={"page": 10, "page_size": 20},
        )
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"] == []


# ═══════════════════════════════════════════════════════════════════
# 获取详情（GET /{id}）
# ═══════════════════════════════════════════════════════════════════


class TestGetSku:
    """GET /api/skus/{id} 相关测试。"""

    async def test_get_sku_detail(self, async_client):
        """获取存在的 SKU，返回详情（含所属产品信息）。"""
        product = await _create_product(async_client, "详情产品")

        # 创建 SKU
        create_resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-DETAIL",
                "price": "88.88",
                "stock": 50,
                "attrs": {"颜色": "白色"},
                "image_url": "https://example.com/detail.jpg",
            },
        )
        sku_id = create_resp.json()["data"]["id"]

        # 获取详情
        resp = await async_client.get(f"/api/skus/{sku_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["id"] == sku_id
        assert data["sku_code"] == "SKU-DETAIL"
        assert float(data["price"]) == 88.88
        assert data["stock"] == 50
        # 所属产品信息正确
        assert data["product"] is not None
        assert data["product"]["id"] == product["id"]
        assert data["product"]["name"] == "详情产品"

    async def test_get_sku_not_found(self, async_client):
        """获取不存在的 SKU ID，应返回 404。"""
        resp = await async_client.get("/api/skus/9999")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "404001"  # NOT_FOUND


# ═══════════════════════════════════════════════════════════════════
# 更新 SKU（PUT）
# ═══════════════════════════════════════════════════════════════════


class TestUpdateSku:
    """PUT /api/skus/{id} 相关测试。"""

    async def test_update_sku_partial(self, async_client):
        """部分更新：只改 price 和 stock，其他字段保持不变。"""
        product = await _create_product(async_client, "部分更新产品")

        create_resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-PARTIAL",
                "price": "10.00",
                "stock": 10,
                "attrs": {"颜色": "红色"},
                "image_url": "https://example.com/old.jpg",
            },
        )
        sku_id = create_resp.json()["data"]["id"]

        # 只更新 price 和 stock
        resp = await async_client.put(
            f"/api/skus/{sku_id}",
            json={
                "price": "20.00",
                "stock": 99,
            },
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert float(data["price"]) == 20.00
        assert data["stock"] == 99
        # 未更新的字段保持不变
        assert data["sku_code"] == "SKU-PARTIAL"
        assert data["attrs"] == {"颜色": "红色"}
        assert data["image_url"] == "https://example.com/old.jpg"

    async def test_update_sku_all_fields(self, async_client):
        """更新所有可更新字段。"""
        product = await _create_product(async_client, "全字段更新产品")

        create_resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-ALL-OLD",
                "price": "10.00",
                "stock": 10,
                "attrs": {"颜色": "旧"},
                "image_url": "https://example.com/old.jpg",
            },
        )
        sku_id = create_resp.json()["data"]["id"]

        resp = await async_client.put(
            f"/api/skus/{sku_id}",
            json={
                "sku_code": "SKU-ALL-NEW",
                "price": "99.99",
                "stock": 100,
                "attrs": {"颜色": "新", "尺寸": "M"},
                "image_url": "https://example.com/new.jpg",
            },
        )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["sku_code"] == "SKU-ALL-NEW"
        assert float(data["price"]) == 99.99
        assert data["stock"] == 100
        assert data["attrs"] == {"颜色": "新", "尺寸": "M"}
        assert data["image_url"] == "https://example.com/new.jpg"

    async def test_update_sku_not_found(self, async_client):
        """更新不存在的 SKU ID，应返回 404。"""
        resp = await async_client.put(
            "/api/skus/9999",
            json={"price": "99.00"},
        )

        assert resp.status_code == 404
        assert resp.json()["code"] == "404001"

    async def test_update_sku_negative_price_validation(self, async_client):
        """更新时 price 为负数，应返回 422 校验错误。"""
        product = await _create_product(async_client, "负价更新产品")

        create_resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-NEG-UPD",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )
        sku_id = create_resp.json()["data"]["id"]

        resp = await async_client.put(
            f"/api/skus/{sku_id}",
            json={"price": "-5.00"},
        )

        assert resp.status_code == 422

    async def test_update_sku_duplicate_code(self, async_client):
        """更新 sku_code 为已存在的编码，应返回 409 唯一约束冲突。"""
        product = await _create_product(async_client, "重复编码更新产品")

        # 创建两个 SKU
        await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-A",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/a.jpg",
            },
        )
        sku_b_resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-B",
                "price": "20.00",
                "attrs": {},
                "image_url": "https://example.com/b.jpg",
            },
        )
        sku_b_id = sku_b_resp.json()["data"]["id"]

        # 将 SKU-B 的编码更新为 SKU-A（已存在）
        resp = await async_client.put(
            f"/api/skus/{sku_b_id}",
            json={"sku_code": "SKU-A"},
        )

        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "500101"  # DB_UNIQUE_CONFLICT


# ═══════════════════════════════════════════════════════════════════
# 删除 SKU（DELETE）
# ═══════════════════════════════════════════════════════════════════


class TestDeleteSku:
    """DELETE /api/skus/{id} 相关测试。"""

    async def test_delete_sku_success(self, async_client):
        """删除存在的 SKU，返回 204 No Content。"""
        product = await _create_product(async_client, "删除测试产品")

        create_resp = await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-DELETE",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )
        sku_id = create_resp.json()["data"]["id"]

        resp = await async_client.delete(f"/api/skus/{sku_id}")

        # 204 No Content：HTTP 规范不允许有 body，中间件已跳过包装
        assert resp.status_code == 204

        # 再次查询应返回 404
        resp = await async_client.get(f"/api/skus/{sku_id}")
        assert resp.status_code == 404

    async def test_delete_sku_not_found(self, async_client):
        """删除不存在的 SKU ID，应返回 404。"""
        resp = await async_client.delete("/api/skus/9999")

        assert resp.status_code == 404
        assert resp.json()["code"] == "404001"


# ═══════════════════════════════════════════════════════════════════
# 级联删除验证
# ═══════════════════════════════════════════════════════════════════


class TestSkuCascadeDelete:
    """验证删除产品时 SKU 被级联删除（CASCADE ondelete）。"""

    async def test_product_delete_cascades_to_skus(self, async_client):
        """删除产品后，其下所有 SKU 应被数据库层 ON DELETE CASCADE 自动删除。

        核心验证点：
        1. DELETE 返回 204 — 证明 passive_deletes 配置生效，SQLAlchemy 不再尝试
           UPDATE sku SET product_id=NULL（违反 NOT NULL 约束的 IntegrityError）
        2. SKU 列表 total 减少 — 证明 DB 层 ON DELETE CASCADE 真的删了 SKU 记录
        """
        # 记录 SKU 数量（删除前基线）
        before = await async_client.get("/api/skus")
        before_total = before.json()["data"]["total"]

        # 创建产品并关联 3 个 SKU
        product_resp = await async_client.post(
            "/api/products",
            json={"name": "级联删除产品"},
        )
        product_id = product_resp.json()["data"]["id"]

        for i in range(3):
            await async_client.post(
                "/api/skus",
                json={
                    "product_id": product_id,
                    "sku_code": f"SKU-CASCADE-{i}",
                    "price": "10.00",
                    "attrs": {},
                    "image_url": "https://example.com/img.jpg",
                },
            )

        # 确认 3 个 SKU 创建成功
        r = await async_client.get("/api/skus")
        assert r.json()["data"]["total"] == before_total + 3

        # 删除产品 —— 关键：passive_deletes 未配置时会触发 IntegrityError → 500
        resp = await async_client.delete(f"/api/products/{product_id}")
        assert resp.status_code == 204, (
            f"DELETE 应返回 204（级联删除成功），"
            f"实际返回 {resp.status_code}：{resp.text}"
        )

        # 验证 CASCADE 删除：SKU 总数回到基线
        r = await async_client.get("/api/skus")
        assert r.json()["data"]["total"] == before_total


# ═══════════════════════════════════════════════════════════════════
# 多用例间隔离验证
# ═══════════════════════════════════════════════════════════════════


class TestSkuIsolation:
    """验证 cleanup_db autouse fixture 确实在每个用例后清空了数据。"""

    async def test_case_a_creates_data(self, async_client):
        """用例 A 创建一个产品和一个 SKU。"""
        product = await _create_product(async_client, "A创建的产品")
        await async_client.post(
            "/api/skus",
            json={
                "product_id": product["id"],
                "sku_code": "SKU-ISO-A",
                "price": "10.00",
                "attrs": {},
                "image_url": "https://example.com/img.jpg",
            },
        )
        resp = await async_client.get("/api/skus")
        assert resp.json()["data"]["total"] == 1

    async def test_case_b_starts_fresh(self, async_client):
        """用例 B 开始时数据库应是空的（用例 A 的数据已被 TRUNCATE）。"""
        resp = await async_client.get("/api/skus")
        assert (
            resp.json()["data"]["total"] == 0
        ), "用例 A 创建的数据应已被 cleanup fixture TRUNCATE"
