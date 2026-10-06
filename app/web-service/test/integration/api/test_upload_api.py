"""
文件上传 API 集成测试。

通过 async_client 走真实 HTTP，
验证路由 wiring / 响应序列化 / 统一响应格式 / 异常处理（422 校验错误）。
"""

import os
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.schema.setting_item import SettingItemUpdate
from web_service.service.setting_item import SettingItemService

UPLOAD_SIGN_URL = "/api/upload/sign"


def _oss_settings_from_env() -> list[SettingItemUpdate]:
    """准备 OSS 配置的 payload，从环境变量读取配置值。"""
    return [
        SettingItemUpdate(key="oss_endpoint", value=os.environ["OSS_ENDPOINT"]),
        SettingItemUpdate(
            key="oss_access_key_id", value=os.environ["OSS_ACCESS_KEY_ID"]
        ),
        SettingItemUpdate(
            key="oss_access_key_secret", value=os.environ["OSS_ACCESS_KEY_SECRET"]
        ),
        SettingItemUpdate(key="oss_bucket_name", value=os.environ["OSS_BUCKET_NAME"]),
        SettingItemUpdate(
            key="oss_bucket_domain", value=os.environ.get("OSS_BUCKET_DOMAIN", "")
        ),
    ]


async def _init_oss_settings(db_session: AsyncSession):
    """确保 OSS 种子数据存在并从环境变量更新配置值。

    配置表已被 _force_cleanup 跳过，种子在 pytest_sessionstart 时初始化一次即可。
    这里仍调用 init_settings 做幂等校验，确保 key 存在，再更新 value。
    """
    svc = SettingItemService(db_session)
    await svc.init_settings()
    await svc.update_settings(_oss_settings_from_env())
    await db_session.commit()


class TestGetUploadSign:
    """POST /api/upload/sign 测试。"""

    @pytest.mark.smoke
    async def test_post_returns_credentials(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """正常场景：请求图片类型文件，返回有效的 OSS 上传凭证。"""
        await _init_oss_settings(db_session)

        response = await async_client.post(
            UPLOAD_SIGN_URL,
            json={"filename": "photo.png", "file_size": 1024},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "0"
        data = body["data"]
        assert data["host"]
        assert data["access_id"]
        assert data["policy"]
        assert data["signature"]
        assert data["key"]
        assert data["content_type"] == "image/png"
        assert "bucket_domain" in data

    async def test_jpg_returns_jpeg_content_type(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """JPG 文件返回 image/jpeg MIME 类型。"""
        await _init_oss_settings(db_session)

        response = await async_client.post(
            UPLOAD_SIGN_URL,
            json={"filename": "photo.jpg", "file_size": 2048},
        )
        assert response.status_code == 200
        assert response.json()["data"]["content_type"] == "image/jpeg"

    async def test_webp_returns_credentials(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """WebP 文件返回 image/webp MIME 类型。"""
        await _init_oss_settings(db_session)

        response = await async_client.post(
            UPLOAD_SIGN_URL,
            json={"filename": "image.webp", "file_size": 5120},
        )
        assert response.status_code == 200
        assert response.json()["data"]["content_type"] == "image/webp"

    async def test_bucket_domain_in_response(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """响应中包含 bucket_domain 字段。"""
        await _init_oss_settings(db_session)

        response = await async_client.post(
            UPLOAD_SIGN_URL,
            json={"filename": "photo.png", "file_size": 1024},
        )
        assert response.status_code == 200
        assert "bucket_domain" in response.json()["data"]

    async def test_empty_filename_rejected(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """空文件名触发 422 校验错误。"""
        await _init_oss_settings(db_session)

        response = await async_client.post(
            UPLOAD_SIGN_URL,
            json={"filename": "", "file_size": 1024},
        )
        assert response.status_code == 422

    async def test_zero_file_size_rejected(
        self, db_session: AsyncSession, async_client: AsyncClient
    ):
        """零文件大小触发 422 校验错误。"""
        await _init_oss_settings(db_session)

        response = await async_client.post(
            UPLOAD_SIGN_URL,
            json={"filename": "photo.png", "file_size": 0},
        )
        assert response.status_code == 422
