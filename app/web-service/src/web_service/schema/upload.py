"""文件上传相关的 DTO 定义。

用于 OSS 直传上传场景：
- UploadSignRequest：客户端请求上传签名的入参
- UploadSignResponse：服务端返回的 OSS 上传凭证
"""

from pydantic import Field
from web_service.schema.base import BaseSchema


class UploadSignRequest(BaseSchema):
    """获取上传签名的请求体。"""

    filename: str = Field(min_length=1, description="文件名，如 photo.png")
    file_size: int = Field(gt=0, description="文件大小，单位字节")


class UploadSignResponse(BaseSchema):
    """OSS 直传上传凭证响应体，客户端据此构造 multipart 表单直传 OSS。"""

    host: str = Field(description="OSS Bucket 域名，表单 POST 的目标地址")
    access_id: str = Field(description="OSSAccessKeyId，表单字段")
    policy: str = Field(description="Base64 编码的策略文档，表单字段")
    signature: str = Field(description="策略的 HMAC-SHA1 签名，表单字段")
    key: str = Field(description="文件在 OSS 中的最终路径")
    content_type: str = Field(description="文件的 MIME 类型")
    bucket_domain: str = Field(description="Bucket 的公开访问域名，用于拼接文件 URL")
