import os
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.model.category import Category
from web_service.model.product import Product
from web_service.model.setting_item import SettingItem
from web_service.model.setting_group import SettingGroup
from web_service.model.sku import Sku
from web_service.model.user import User


async def _get_user_by_username(db_session: AsyncSession, username: str) -> User | None:
    result = await db_session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def _seed_ai_settings(db_session: AsyncSession) -> None:
    """幂等写入 AI 配置：settinggroup/settingitem 在 cleanup 中被跳过保留种子，
    所以先查再 upsert，避免唯一约束冲突。"""
    result = await db_session.execute(
        select(SettingGroup).where(SettingGroup.key == "ai")
    )
    group = result.scalar_one_or_none()
    if group is None:
        group = SettingGroup(key="ai", display_name="ai", description="")
        db_session.add(group)
        await db_session.flush()

    ai_settings = [
        # 真实 AI 服务
        # ("ai_api_key", os.environ["AI_API_KEY"]),
        # ("ai_base_url", os.environ["AI_BASE_URL"]),
        # ("ai_model", os.environ["AI_MODEL"]),
        # mock 的 AI 服务
        ("ai_api_key", "mock-api-key"),
        ("ai_base_url", "http://localhost:18001"),
        ("ai_model", "mock-model"),
    ]
    for key, value in ai_settings:
        item_result = await db_session.execute(
            select(SettingItem).where(SettingItem.key == key)
        )
        item = item_result.scalar_one_or_none()
        if item is not None:
            item.value = value
        else:
            db_session.add(SettingItem(key=key, value=value, group_id=group.id))
    await db_session.flush()


async def _create_product_with_category_and_sku(
    db_session: AsyncSession, name: str = "测试产品"
) -> Product:
    cat = Category(name="测试分类")
    db_session.add(cat)
    await db_session.flush()

    product = Product(name=name, description="产品描述", brand="测试品牌")
    product.categories.append(cat)
    db_session.add(product)
    await db_session.flush()

    sku = Sku(
        product_id=product.id,
        sku_code="TEST-001",
        price=Decimal("99.00"),
        stock=100,
        attrs={"color": "red"},
        image_url="https://example.com/img.png",
    )
    db_session.add(sku)
    await db_session.flush()
    return product


async def _mock_chat_stream_chunks(chunks: list[str]):
    for chunk in chunks:
        yield chunk


AI_CONVERSATION_URL = "/api/ai/conversation"


class TestGetConversationHistory:
    @pytest.mark.smoke
    async def test_requires_auth(self, async_client: AsyncClient):
        response = await async_client.get(f"{AI_CONVERSATION_URL}/1")
        assert response.status_code == 401

    async def test_empty_when_no_conversation(
        self, db_session: AsyncSession, async_client: AsyncClient, auth_headers: dict
    ):
        response = await async_client.get(
            f"{AI_CONVERSATION_URL}/1", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        assert body["data"] == []

    async def test_returns_history_after_initialize(
        self, db_session: AsyncSession, async_client: AsyncClient, auth_headers: dict
    ):
        user = await _get_user_by_username(db_session, "testuser")
        assert user is not None
        await _seed_ai_settings(db_session)
        product = await _create_product_with_category_and_sku(db_session)

        mock_instance = MagicMock()
        mock_instance.chat_stream = lambda messages: _mock_chat_stream_chunks(
            ["你好，这是AI回复"]
        )

        from web_service.service.ai_service import AiService

        svc = AiService(db_session)
        with patch("web_service.service.ai_service.AIChat", return_value=mock_instance):
            read_result = await svc.read_initialize(user.id, product.id)
            full_response = ""
            async for chunk in svc.initialize_stream(read_result):
                full_response += chunk
            await svc.write_initialize(read_result, full_response)
            await db_session.commit()

        response = await async_client.get(
            f"{AI_CONVERSATION_URL}/{product.id}", headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        data = body["data"]
        assert len(data) == 1
        assert data[0]["role"] == "assistant"
        assert data[0]["content"] == "你好，这是AI回复"


class TestDeleteConversation:
    @pytest.mark.smoke
    async def test_requires_auth(self, async_client: AsyncClient):
        response = await async_client.delete(f"{AI_CONVERSATION_URL}/1")
        assert response.status_code == 401

    async def test_deletes_conversation(
        self, db_session: AsyncSession, async_client: AsyncClient, auth_headers: dict
    ):
        user = await _get_user_by_username(db_session, "testuser")
        assert user is not None
        await _seed_ai_settings(db_session)
        product = await _create_product_with_category_and_sku(db_session)

        mock_instance = MagicMock()
        mock_instance.chat_stream = lambda messages: _mock_chat_stream_chunks(
            ["AI初始化回复"]
        )

        from web_service.service.ai_service import AiService

        svc = AiService(db_session)
        with patch("web_service.service.ai_service.AIChat", return_value=mock_instance):
            read_result = await svc.read_initialize(user.id, product.id)
            full_response = ""
            async for chunk in svc.initialize_stream(read_result):
                full_response += chunk
            await svc.write_initialize(read_result, full_response)
            await db_session.commit()

        response = await async_client.delete(
            f"{AI_CONVERSATION_URL}/{product.id}", headers=auth_headers
        )
        assert response.status_code == 204

        response = await async_client.get(
            f"{AI_CONVERSATION_URL}/{product.id}", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["data"] == []

    async def test_noop_when_no_conversation(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        response = await async_client.delete(
            f"{AI_CONVERSATION_URL}/99999", headers=auth_headers
        )
        assert response.status_code == 204
