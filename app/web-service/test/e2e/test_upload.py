"""
文件上传 API 端到端测试。

通过 HTTP 请求完整验证文件上传签名接口的：
1. 正常场景（图片类型，返回有效凭证）
2. 错误场景（非图片类型，返回 422 校验错误）

运行方式：
    uv run --package web-service pytest test/e2e/test_upload.py -v
"""

import os
import pytest
from httpx import AsyncClient

UPLOAD_SIGN_URL = "/api/upload/sign"
SETTINGS_URL = "/api/settings/items"


def _oss_settings_payload() -> list[dict]:
    """准备 OSS 配置的 payload，从环境变量读取配置值。"""
    return [
        {"key": "oss_endpoint", "value": os.environ["OSS_ENDPOINT"]},
        {"key": "oss_access_key_id", "value": os.environ["OSS_ACCESS_KEY_ID"]},
        {
            "key": "oss_access_key_secret",
            "value": os.environ["OSS_ACCESS_KEY_SECRET"],
        },
        {"key": "oss_bucket_name", "value": os.environ["OSS_BUCKET_NAME"]},
        {
            "key": "oss_bucket_domain",
            "value": os.environ.get("OSS_BUCKET_DOMAIN", ""),
        },
    ]


class TestUploadSign:
    """POST /api/upload/sign 相关测试。"""

    @pytest.mark.smoke
    async def test_post_returns_credentials(self, async_client: AsyncClient):
        """正常场景：请求图片类型文件，返回有效的 OSS 上传凭证。

        测试流程：
        1. 先通过 /api/settings 接口设置 OSS 配置
        2. 调用 /api/upload/sign 获取签名
        3. 验证返回的凭证包含所有必需字段
        """
        await async_client.put(SETTINGS_URL, json=_oss_settings_payload())

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

    async def test_non_image_rejected(self, async_client: AsyncClient):
        """错误场景：非图片类型文件，返回 422 校验错误。

        测试流程：
        1. 先设置 OSS 配置
        2. 请求 PDF 文件类型
        3. 验证返回 422 状态码和错误消息
        """
        await async_client.put(SETTINGS_URL, json=_oss_settings_payload())

        response = await async_client.post(
            UPLOAD_SIGN_URL,
            json={"filename": "doc.pdf", "file_size": 1024},
        )
        assert response.status_code == 422
        assert "仅支持图片格式" in response.json()["message"]
