"""阿里云 OSS 上传工具的单元测试。

测试覆盖：上传凭证生成（字段、策略、过期时间、异常处理）、文件删除、文件存在性检查。
使用 mock 替代真实 OSS 调用。
"""

import base64
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from web_utils.upload.aliyun import AliyunOSSConfig, AliyunOSSUploader


@pytest.fixture
def config():
    """创建测试用的 OSS 配置实例。"""
    return AliyunOSSConfig(
        access_key_id="test-access-key-id",
        access_key_secret="test-access-key-secret",
        bucket_name="test-bucket",
        endpoint="oss-cn-hangzhou.aliyuncs.com",
        mime_types=["image/png", "application/pdf"],
    )


@pytest.fixture
def uploader(config):
    """创建使用 mock Bucket 的上传器实例，避免真实 OSS 调用。"""
    with (
        patch("web_utils.upload.aliyun.oss2.Auth") as mock_auth,
        patch("web_utils.upload.aliyun.oss2.Bucket") as mock_bucket,
    ):
        uploader = AliyunOSSUploader(config)
        uploader._bucket = mock_bucket.return_value
        yield uploader


class TestGenerateUploadCredentials:
    """generate_upload_credentials 方法的测试：验证凭证生成的正确性和异常处理。"""

    def test_successful_credential_generation(self, config):
        """验证正常流程生成的凭证包含所有必要字段，且值正确。"""
        with (
            patch("web_utils.upload.aliyun.oss2.Auth"),
            patch("web_utils.upload.aliyun.oss2.Bucket"),
            patch("web_utils.upload.aliyun.uuid.uuid4") as mock_uuid,
            patch("web_utils.upload.aliyun.datetime") as mock_dt,
            patch("web_utils.upload.dir_strategy.datetime") as mock_dir_dt,
        ):
            mock_uuid.return_value.hex = "a1b2c3d4e5f6"
            mock_dt.now.return_value = datetime(
                2025, 6, 26, 10, 0, 0, tzinfo=timezone.utc
            )
            mock_dir_dt.now.return_value = datetime(2025, 6, 26, 10, 0, 0)

            uploader = AliyunOSSUploader(config)
            result = uploader.generate_upload_credentials("photo.png", 102400)

        assert result["host"] == "https://test-bucket.oss-cn-hangzhou.aliyuncs.com"
        assert result["access_id"] == "test-access-key-id"
        assert result["content_type"] == "image/png"
        assert result["key"] == "uploads/2025/06/26/a1b2c3d4e5f6.png"
        assert result["policy"] is not None
        assert result["signature"] is not None

    def test_policy_contains_exact_key_match(self, config):
        """验证 policy 中包含精确匹配 key、Content-Type 和文件大小限制的条件。"""
        with (
            patch("web_utils.upload.aliyun.oss2.Auth"),
            patch("web_utils.upload.aliyun.oss2.Bucket"),
            patch("web_utils.upload.aliyun.uuid.uuid4") as mock_uuid,
            patch("web_utils.upload.aliyun.datetime") as mock_dt,
        ):
            mock_uuid.return_value.hex = "a1b2c3d4e5f6"
            mock_dt.now.return_value = datetime(
                2025, 6, 26, 10, 0, 0, tzinfo=timezone.utc
            )

            uploader = AliyunOSSUploader(config)
            result = uploader.generate_upload_credentials("photo.png", 102400)

        policy_json = base64.b64decode(result["policy"]).decode()
        policy_dict = json.loads(policy_json)
        conditions = policy_dict["conditions"]

        assert ["eq", "$key", result["key"]] in conditions
        assert ["eq", "$Content-Type", "image/png"] in conditions
        assert ["content-length-range", 0, 102400] in conditions

    def test_default_expire_one_hour(self, config):
        """验证默认过期时间为 1 小时。"""
        with (
            patch("web_utils.upload.aliyun.oss2.Auth"),
            patch("web_utils.upload.aliyun.oss2.Bucket"),
            patch("web_utils.upload.aliyun.uuid.uuid4") as mock_uuid,
            patch("web_utils.upload.aliyun.datetime") as mock_dt,
        ):
            mock_uuid.return_value.hex = "a1b2c3d4e5f6"
            mock_dt.now.return_value = datetime(
                2025, 6, 26, 10, 0, 0, tzinfo=timezone.utc
            )

            uploader = AliyunOSSUploader(config)
            result = uploader.generate_upload_credentials("photo.png", 102400)

        policy_json = base64.b64decode(result["policy"]).decode()
        policy_dict = json.loads(policy_json)

        assert policy_dict["expiration"] == "2025-06-26T11:00:00.000Z"

    def test_raises_on_missing_suffix(self, config):
        """验证无后缀文件名抛出 ValueError。"""
        with (
            patch("web_utils.upload.aliyun.oss2.Auth"),
            patch("web_utils.upload.aliyun.oss2.Bucket"),
        ):
            uploader = AliyunOSSUploader(config)
            with pytest.raises(ValueError, match="无法获取文件后缀"):
                uploader.generate_upload_credentials("noext", 1024)

    def test_raises_on_unsupported_type(self, config):
        """验证不支持的文件类型抛出 ValueError。"""
        with (
            patch("web_utils.upload.aliyun.oss2.Auth"),
            patch("web_utils.upload.aliyun.oss2.Bucket"),
        ):
            uploader = AliyunOSSUploader(config)
            with pytest.raises(ValueError, match="不支持的文件类型"):
                uploader.generate_upload_credentials("file.xyz", 1024)

    def test_raises_on_not_allowed_mime_type(self, config):
        """验证不在配置的 mime_types 列表中的类型抛出 ValueError。"""
        config.mime_types = ["application/pdf"]
        with (
            patch("web_utils.upload.aliyun.oss2.Auth"),
            patch("web_utils.upload.aliyun.oss2.Bucket"),
        ):
            uploader = AliyunOSSUploader(config)
            with pytest.raises(ValueError, match="不允许上传的类型"):
                uploader.generate_upload_credentials("photo.png", 1024)

    def test_path_filename_extracts_basename(self, config):
        """验证带路径的文件名能正确提取文件名和后缀。"""
        with (
            patch("web_utils.upload.aliyun.oss2.Auth"),
            patch("web_utils.upload.aliyun.oss2.Bucket"),
            patch("web_utils.upload.aliyun.uuid.uuid4") as mock_uuid,
            patch("web_utils.upload.aliyun.datetime") as mock_dt,
        ):
            mock_uuid.return_value.hex = "a1b2c3d4e5f6"
            mock_dt.now.return_value = datetime(
                2025, 6, 26, 10, 0, 0, tzinfo=timezone.utc
            )

            uploader = AliyunOSSUploader(config)
            result = uploader.generate_upload_credentials("/a/b/c/report.pdf", 1024)

        assert result["content_type"] == "application/pdf"
        assert result["key"].endswith(".pdf")

    def test_doc_file_type(self, config):
        """验证 PDF 文档类型的 content_type 正确。"""
        with (
            patch("web_utils.upload.aliyun.oss2.Auth"),
            patch("web_utils.upload.aliyun.oss2.Bucket"),
            patch("web_utils.upload.aliyun.uuid.uuid4") as mock_uuid,
            patch("web_utils.upload.aliyun.datetime") as mock_dt,
        ):
            mock_uuid.return_value.hex = "a1b2c3d4e5f6"
            mock_dt.now.return_value = datetime(
                2025, 6, 26, 10, 0, 0, tzinfo=timezone.utc
            )

            uploader = AliyunOSSUploader(config)
            result = uploader.generate_upload_credentials("doc.pdf", 2048)

        assert result["content_type"] == "application/pdf"


class TestDelete:
    """delete 方法的测试：验证文件删除调用。"""

    async def test_delete_calls_bucket_delete_object(self, uploader):
        """验证 delete 方法调用了 bucket.delete_object 并传入正确的 key。"""
        with patch("web_utils.upload.aliyun.asyncio.to_thread") as mock_to_thread:
            await uploader.delete("uploads/2025/06/26/test.png")
            mock_to_thread.assert_called_once_with(
                uploader._bucket.delete_object, "uploads/2025/06/26/test.png"
            )


class TestExists:
    """exists 方法的测试：验证文件存在性检查。"""

    async def test_exists_true(self, uploader):
        """验证文件存在时返回 True。"""
        with patch("web_utils.upload.aliyun.asyncio.to_thread", return_value=True):
            result = await uploader.exists("uploads/2025/06/26/test.png")
            assert result is True

    async def test_exists_false(self, uploader):
        """验证文件不存在时返回 False。"""
        with patch("web_utils.upload.aliyun.asyncio.to_thread", return_value=False):
            result = await uploader.exists("uploads/2025/06/26/test.png")
            assert result is False
