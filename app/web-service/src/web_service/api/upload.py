"""
文件上传 API 路由。

提供 OSS 直传上传凭证获取：
- POST   /api/upload/sign     获取上传签名（客户端据此直传 OSS）
"""

from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.core.database import get_session
from web_service.schema.upload import UploadSignRequest, UploadSignResponse
from web_service.service.upload import UploadService

router = APIRouter(prefix="/api/upload", tags=["文件上传"])


@router.post(
    "/sign",
    response_model=UploadSignResponse,
    status_code=status.HTTP_200_OK,
    summary="获取上传签名",
    description="客户端上传文件前，先调用此接口获取 OSS 上传凭证（含签名、策略等），然后客户端直传 OSS。",
)
async def get_upload_sign(
    data: UploadSignRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """根据文件名和大小生成 OSS 直传上传凭证。

    Args:
        data: 上传签名请求体，包含 filename 和 file_size
        db: 异步数据库会话，通过依赖注入获取

    Returns:
        UploadSignResponse: OSS 上传凭证（host、policy、signature、key 等）
    """
    service = UploadService(db)
    return await service.generate_upload_sign(
        filename=data.filename, file_size=data.file_size
    )
