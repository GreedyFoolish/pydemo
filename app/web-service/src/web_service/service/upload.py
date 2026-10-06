"""
文件上传 Service 实现。

基于阿里云 OSS PostObject 直传模式：
1. 从数据库读取 OSS 配置（setting_group: aliyun_oss）
2. 调用 AliyunOSSUploader 生成上传凭证
3. 返回凭证供客户端直传 OSS
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from web_utils.shared.file_util import get_suffix
from web_utils.shared.mime import IMAGE_MIME, get_mime_type
from web_utils.upload.aliyun import AliyunOSSConfig, AliyunOSSUploader
from web_service.exception.upload import UploadException
from web_service.exception.codes import ErrorCode
from web_service.model.setting_group import SettingGroup


class UploadService:
    """文件上传业务服务。

    负责从数据库读取 OSS 配置，校验文件类型，生成 OSS 直传凭证。
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    async def _get_oss_settings(self) -> dict[str, str]:
        """从数据库查询 aliyun_oss 配置组及其所有配置项。

        返回:
            以 key->value 形式组织的配置字典

        异常:
            UploadException: 配置组不存在或必需配置项缺失时
        """
        result = await self._db.execute(
            select(SettingGroup)
            .options(selectinload(SettingGroup.items))
            .where(SettingGroup.key == "aliyun_oss")
        )
        group = result.unique().scalar_one_or_none()
        if group is None:
            raise UploadException(
                error_code=ErrorCode.INTERNAL_ERROR,
                message="OSS 上传配置未初始化",
            )

        settings_map = {s.key: s.value for s in group.items}
        required = {
            "oss_endpoint",
            "oss_access_key_id",
            "oss_access_key_secret",
            "oss_bucket_name",
        }
        for key in required:
            if not settings_map.get(key):
                raise UploadException(
                    error_code=ErrorCode.INTERNAL_ERROR,
                    message=f"OSS 配置缺失: {key}",
                )
        return settings_map

    async def generate_upload_sign(self, filename: str, file_size: int) -> dict:
        """生成 OSS 直传上传凭证。

        校验文件后缀和 MIME 类型（仅允许图片），从数据库读取 OSS 配置，
        调用 AliyunOSSUploader 生成签名凭证，并附加 bucket_domain。

        参数:
            filename: 文件名，如 photo.png
            file_size: 文件大小，单位字节

        返回:
            上传凭证字典（host、access_id、policy、signature、key、content_type、bucket_domain）

        异常:
            UploadException: 文件后缀无效、类型不支持或 OSS 配置缺失时
        """
        suffix = get_suffix(filename)
        if suffix is None:
            raise UploadException(
                error_code=ErrorCode.VALIDATION_FILE_ERROR,
                message=f"无法获取文件后缀: {filename}",
            )

        content_type = get_mime_type(suffix)
        if content_type is None:
            raise UploadException(
                error_code=ErrorCode.VALIDATION_FILE_ERROR,
                message=f"不支持的文件类型: .{suffix}",
            )

        if content_type not in IMAGE_MIME.values():
            raise UploadException(
                error_code=ErrorCode.VALIDATION_FILE_ERROR,
                message=f"不支持的文件类型: {suffix}, 仅支持图片格式",
            )

        oss_settings = await self._get_oss_settings()

        config = AliyunOSSConfig(
            access_key_id=oss_settings["oss_access_key_id"],
            access_key_secret=oss_settings["oss_access_key_secret"],
            bucket_name=oss_settings["oss_bucket_name"],
            endpoint=oss_settings["oss_endpoint"],
            mime_types=list(IMAGE_MIME.values()),
        )

        uploader = AliyunOSSUploader(config)
        credentials = uploader.generate_upload_credentials(filename, file_size)

        # 拼接 bucket 公开访问域名，未配置协议前缀时补 //（协议相对 URL）
        bucket_domain = oss_settings.get("oss_bucket_domain", "")
        if bucket_domain and not bucket_domain.startswith(("http://", "https://")):
            bucket_domain = f"//{bucket_domain}"

        credentials["bucket_domain"] = bucket_domain
        return credentials
