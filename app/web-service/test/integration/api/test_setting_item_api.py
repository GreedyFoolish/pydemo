"""
SettingItem API 集成测试。

通过 async_client 走真实 HTTP，
验证 5 个端点的路由 wiring / 响应序列化 / 统一响应格式 / 异常处理。

每个测试函数开头调 _prepare_seed_data() 准备种子数据（绕过 cleanup_db 清库）。
所有测试中动态获取 group_id / item_id，不依赖种子数据的具体数量和顺序。
"""

from web_service.exception import ErrorCode


async def _prepare_seed_data():
    """在 pytest 进程里通过 SettingItemService.init_settings 准备种子数据。

    cleanup_db 会把数据库清干净，API 测试走的是真实服务器的 HTTP，
    所以需要 pytest 进程和服务器进程共用同一个测试库，在这里手动准备数据。
    """
    from web_service.core.database import get_session_factory
    from web_service.service.setting_item import SettingItemService

    factory = get_session_factory()
    async with factory() as session:
        service = SettingItemService(session)
        await service.init_settings()
        await session.commit()


async def _get_first_item_and_group(async_client):
    """通过 GET /items/all 动态获取第一个 item 及其 group 的信息。

    返回 (item_id, group_id, item_key) 三元组，供后续测试拼接 URL。
    """
    resp = await async_client.get("/api/settings/items/all")
    data = resp.json()["data"]
    first = data["items"][0]
    return first["id"], first["group"]["id"], first["key"]


# ═══════════════════════════════════════════════════════════════════
# GET /api/settings/items/all 测试
# ═══════════════════════════════════════════════════════════════════


class TestGetAllItems:
    """GET /api/settings/items/all 测试。"""

    async def test_returns_all_with_group(self, async_client):
        """全量返回，每个 item 带 group 信息，结构符合 SettingItemAllResponse。"""
        await _prepare_seed_data()

        resp = await async_client.get("/api/settings/items/all")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"

        data = body["data"]
        assert data["total_count"] > 0  # 种子数据肯定有
        assert len(data["items"]) == data["total_count"]

        # 每个 item 都带完整 group 信息
        for item in data["items"]:
            assert item["group"] is not None
            assert item["group"]["id"] is not None
            assert item["group"]["key"] is not None

    async def test_empty_response_when_no_data(self, async_client):
        """空库时返回正确结构（data=空 items + total_count=0）。"""
        resp = await async_client.get("/api/settings/items/all")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert body["data"]["items"] == []
        assert body["data"]["total_count"] == 0


# ═══════════════════════════════════════════════════════════════════
# GET /api/settings/items/group/{group_id} 测试
# ═══════════════════════════════════════════════════════════════════


class TestGetItemsByGroup:
    """GET /api/settings/items/group/{group_id} 测试。"""

    async def test_returns_items_for_group(self, async_client):
        """动态获取 group_id，验证返回该组下的 item。"""
        await _prepare_seed_data()

        _, group_id, _ = await _get_first_item_and_group(async_client)

        resp = await async_client.get(f"/api/settings/items/group/{group_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert len(body["data"]) >= 1  # 至少有动态获取的那个 item

        # 所有返回的 item 都属于这个 group
        for item in body["data"]:
            assert item["group_id"] == group_id

    async def test_empty_when_group_not_found(self, async_client):
        """不存在的 group_id 返回空列表（不报错）。"""
        await _prepare_seed_data()

        resp = await async_client.get("/api/settings/items/group/9999")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ═══════════════════════════════════════════════════════════════════
# GET /api/settings/items/{id} 测试
# ═══════════════════════════════════════════════════════════════════


class TestGetItemById:
    """GET /api/settings/items/{id} 测试。"""

    async def test_found(self, async_client):
        """动态获取 item_id，验证能查到。"""
        await _prepare_seed_data()

        item_id, _, item_key = await _get_first_item_and_group(async_client)

        resp = await async_client.get(f"/api/settings/items/{item_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert body["data"]["id"] == item_id
        assert body["data"]["key"] == item_key

    async def test_not_found(self, async_client):
        """不存在的 id 返回 404 + NOT_FOUND 错误码。"""
        await _prepare_seed_data()

        resp = await async_client.get("/api/settings/items/9999")
        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code


# ═══════════════════════════════════════════════════════════════════
# GET /api/settings/items/filter/ 测试
# ═══════════════════════════════════════════════════════════════════


class TestFilterItems:
    """GET /api/settings/items/filter/ 测试。"""

    async def test_filter_by_key(self, async_client):
        """动态获取一个 item 的 key，按它过滤返回 1 条。"""
        await _prepare_seed_data()

        _, _, item_key = await _get_first_item_and_group(async_client)

        resp = await async_client.get(
            "/api/settings/items/filter/", params={"key": item_key}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert len(body["data"]) == 1
        assert body["data"][0]["key"] == item_key

    async def test_filter_by_group_id(self, async_client):
        """动态获取一个 group_id，按它过滤返回至少 1 条。"""
        await _prepare_seed_data()

        _, group_id, _ = await _get_first_item_and_group(async_client)

        resp = await async_client.get(
            "/api/settings/items/filter/", params={"group_id": group_id}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        for item in data:
            assert item["group_id"] == group_id

    async def test_filter_no_match(self, async_client):
        """没有匹配的返回空列表。"""
        await _prepare_seed_data()

        resp = await async_client.get(
            "/api/settings/items/filter/", params={"key": "nonexistent_xyz_key"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ═══════════════════════════════════════════════════════════════════
# PUT /api/settings/items/{id} 测试
# ═══════════════════════════════════════════════════════════════════


class TestUpdateItem:
    """PUT /api/settings/items/{id} 测试。"""

    async def test_update_value(self, async_client):
        """只更新 value。"""
        await _prepare_seed_data()

        item_id, _, item_key = await _get_first_item_and_group(async_client)

        resp = await async_client.put(
            f"/api/settings/items/{item_id}", json={"value": "新值"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == "0"
        assert body["data"]["value"] == "新值"
        # key 不可修改（schema 里没有），保持不变
        assert body["data"]["key"] == item_key

    async def test_update_display_name(self, async_client):
        """更新 display_name。"""
        await _prepare_seed_data()

        item_id, _, _ = await _get_first_item_and_group(async_client)

        resp = await async_client.put(
            f"/api/settings/items/{item_id}", json={"display_name": "新显示名"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["display_name"] == "新显示名"

    async def test_update_not_found(self, async_client):
        """更新不存在的 item 返回 404 + NOT_FOUND。"""
        await _prepare_seed_data()

        resp = await async_client.put(
            "/api/settings/items/9999", json={"value": "不存在"}
        )
        assert resp.status_code == 404
        assert resp.json()["code"] == ErrorCode.NOT_FOUND.code

    async def test_update_validation_error(self, async_client):
        """display_name 为空触发 422 校验错误。"""
        await _prepare_seed_data()

        item_id, _, _ = await _get_first_item_and_group(async_client)

        resp = await async_client.put(
            f"/api/settings/items/{item_id}", json={"display_name": ""}
        )
        assert resp.status_code == 422
