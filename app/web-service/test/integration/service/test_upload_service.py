"""
文件上传 Service 集成测试。

直接调用 UploadService（通过 db_session fixture），
重点覆盖凭证生成、文件类型校验、OSS 配置缺失等场景。
"""

import os
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.exception.upload import UploadException
from web_service.schema.setting_item import SettingItemUpdate
from web_service.service.setting_item import SettingItemService
from web_service.service.upload import UploadService


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
    """通过 SettingItemService 初始化并更新 OSS 配置。"""
    svc = SettingItemService(db_session)
    await svc.init_settings()
    await svc.update_settings(_oss_settings_from_env())


class TestGenerateUploadSign:
    """UploadService.generate_upload_sign() 正常场景测试。"""

    async def _get_svc(self, db_session: AsyncSession) -> UploadService:
        """初始化 OSS 配置并返回 UploadService 实例。"""
        await _init_oss_settings(db_session)
        return UploadService(db_session)

    @pytest.mark.smoke
    async def test_png_file_returns_credentials(self, db_session: AsyncSession):
        """PNG 文件返回包含所有必需字段的凭证。"""
        svc = await self._get_svc(db_session)
        result = await svc.generate_upload_sign("photo.png", 1024)

        assert result["host"]
        assert result["access_id"]
        assert result["policy"]
        assert result["signature"]
        assert result["key"]
        assert result["content_type"] == "image/png"
        assert "bucket_domain" in result

    async def test_jpg_file_returns_credentials(self, db_session: AsyncSession):
        """JPG 文件返回 image/jpeg MIME 类型。"""
        svc = await self._get_svc(db_session)
        result = await svc.generate_upload_sign("photo.jpg", 2048)
        assert result["content_type"] == "image/jpeg"

    async def test_webp_file_returns_credentials(self, db_session: AsyncSession):
        """WebP 文件返回 image/webp MIME 类型。"""
        svc = await self._get_svc(db_session)
        result = await svc.generate_upload_sign("image.webp", 5120)
        assert result["content_type"] == "image/webp"

    async def test_bucket_domain_returned(self, db_session: AsyncSession):
        """响应中包含 bucket_domain 字段。"""
        svc = await self._get_svc(db_session)
        result = await svc.generate_upload_sign("photo.png", 1024)
        assert "bucket_domain" in result

    async def test_key_starts_with_uploads(self, db_session: AsyncSession):
        """key 以 uploads/ 开头。"""
        svc = await self._get_svc(db_session)
        result = await svc.generate_upload_sign("photo.png", 1024)
        assert result["key"].startswith("uploads/")

    async def test_key_ends_with_correct_suffix(self, db_session: AsyncSession):
        """key 保留原始文件后缀。"""
        svc = await self._get_svc(db_session)
        result = await svc.generate_upload_sign("photo.png", 1024)
        assert result["key"].endswith(".png")


class TestGenerateUploadSignValidation:
    """UploadService.generate_upload_sign() 校验错误测试。"""

    async def _get_svc(self, db_session: AsyncSession) -> UploadService:
        """初始化 OSS 配置并返回 UploadService 实例。"""
        await _init_oss_settings(db_session)
        return UploadService(db_session)

    async def test_no_suffix_rejected(self, db_session: AsyncSession):
        """无后缀文件名抛出 UploadException。"""
        svc = await self._get_svc(db_session)
        with pytest.raises(UploadException) as exc:
            await svc.generate_upload_sign("noextension", 1024)
        assert "无法获取文件后缀" in str(exc.value)

    async def test_pdf_rejected_not_image(self, db_session: AsyncSession):
        """PDF 文件抛出"仅支持图片格式"异常。"""
        svc = await self._get_svc(db_session)
        with pytest.raises(UploadException) as exc:
            await svc.generate_upload_sign("doc.pdf", 1024)
        assert "仅支持图片格式" in str(exc.value)

    async def test_docx_rejected_not_image(self, db_session: AsyncSession):
        """DOCX 文件抛出"仅支持图片格式"异常。"""
        svc = await self._get_svc(db_session)
        with pytest.raises(UploadException) as exc:
            await svc.generate_upload_sign("report.docx", 1024)
        assert "仅支持图片格式" in str(exc.value)

    async def test_unknown_suffix_rejected(self, db_session: AsyncSession):
        """未知后缀抛出"不支持的文件类型"异常。"""
        svc = await self._get_svc(db_session)
        with pytest.raises(UploadException) as exc:
            await svc.generate_upload_sign("file.xyz", 1024)
        assert "不支持的文件类型" in str(exc.value)

    async def test_without_oss_settings_rejected(self, db_session: AsyncSession):
        """OSS 配置的 value 为空时抛出异常。

        settinggroup/settingitem 表不会被 cleanup_db TRUNCATE，种子数据
        （group + item 行）在 pytest_sessionstart 时由 lifespan 写入。
        但种子的 value 默认是空字符串，所以 _get_oss_settings 走的是
        "配置缺失" 分支而非 "group 不存在" 分支。
        """
        svc = UploadService(db_session)
        with pytest.raises(UploadException) as exc:
            await svc.generate_upload_sign("photo.png", 1024)
        assert "OSS 配置缺失" in str(exc.value)
