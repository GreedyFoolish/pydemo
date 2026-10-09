import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.model.user import User

SSE_INIT_URL = "/api/ai/sse/initialize"
SSE_MESSAGE_URL = "/api/ai/sse/message"


class TestInitializeSSE:
    @pytest.mark.smoke
    async def test_requires_auth(self, async_client: AsyncClient):
        response = await async_client.get(f"{SSE_INIT_URL}/1")
        assert response.status_code == 401


class TestSendMessageSSE:
    @pytest.mark.smoke
    async def test_requires_auth(self, async_client: AsyncClient):
        response = await async_client.post(
            SSE_MESSAGE_URL,
            json={"product_id": 1, "content": "你好"},
        )
        assert response.status_code == 401
