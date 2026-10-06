"""
系统设置 e2e 测试——核心查询与更新 happy path。
"""

import pytest

SETTINGS_URL = "/api/settings/items"


@pytest.mark.skip_cleanup
class TestGetSettings:
    """GET /api/settings/items/all 获取所有配置项。"""

    @pytest.mark.smoke
    async def test_get_returns_ok(self, async_client):
        """smoke：正常请求返回 200，data 有 items + total_count 结构。"""
        response = await async_client.get(f"{SETTINGS_URL}/all")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert isinstance(body["data"], dict)
        assert "items" in body["data"]
        assert "total_count" in body["data"]
        assert isinstance(body["data"]["items"], list)
        assert body["data"]["total_count"] == len(body["data"]["items"])
        assert body["data"]["total_count"] > 0  # 种子已写入

    @pytest.mark.smoke
    async def test_item_structure(self, async_client):
        """smoke：返回的 item 有 id / key / value / group 完整结构。"""
        response = await async_client.get(f"{SETTINGS_URL}/all")
        assert response.status_code == 200
        item = response.json()["data"]["items"][0]

        assert "id" in item
        assert "key" in item
        assert "value" in item
        assert "display_name" in item
        assert "group_id" in item
        assert item["group"] is not None
        assert "id" in item["group"]
        assert "key" in item["group"]


@pytest.mark.skip_cleanup
class TestUpdateSettings:
    """PUT /api/settings/items/{id} 更新配置项。"""

    @pytest.mark.smoke
    async def test_put_returns_ok(self, async_client):
        """smoke：先 GET 拿 id，再 PUT 更新 value → 200，key 不变。"""
        get_resp = await async_client.get(f"{SETTINGS_URL}/all")
        first_item = get_resp.json()["data"]["items"][0]
        item_id = first_item["id"]

        put_resp = await async_client.put(
            f"{SETTINGS_URL}/{item_id}",
            json={"value": "e2e_smoke_test_value"},
        )
        assert put_resp.status_code == 200
        body = put_resp.json()
        assert body["code"] == "0"
        assert body["data"]["value"] == "e2e_smoke_test_value"
        assert body["data"]["key"] == first_item["key"]

    @pytest.mark.smoke
    async def test_put_then_get_persists(self, async_client):
        """smoke：PUT 后再 GET 同一个 id，验证数据库真落库了。"""
        get_resp = await async_client.get(f"{SETTINGS_URL}/all")
        first_item = get_resp.json()["data"]["items"][0]
        item_id = first_item["id"]

        await async_client.put(
            f"{SETTINGS_URL}/{item_id}",
            json={"value": "persist_verify"},
        )

        resp = await async_client.get(f"{SETTINGS_URL}/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["data"]["value"] == "persist_verify"
