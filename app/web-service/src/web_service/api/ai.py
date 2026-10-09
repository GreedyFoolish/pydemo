"""
AI 导购 REST API。

提供对话历史查询和管理：
- GET    /conversation/{product_id}    获取对话历史
- DELETE /conversation/{product_id}    删除对话记录

流式接口见 ai_sse.py (SSE) 和 ai_ws.py (WebSocket)。
"""

from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from web_service.core.auth import get_current_user
from web_service.core.database import get_session
from web_service.model.user import User
from web_service.schema.ai import AiMessageItem
from web_service.service.ai_service import AiService

router = APIRouter(prefix="/api/ai", tags=["AI"])


@router.get(
    "/conversation/{product_id}",
    response_model=list[AiMessageItem],
    summary="获取对话历史",
    description="获取指定产品的对话历史，过滤掉 system 消息。",
)
async def get_conversation_history(
    product_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    # 获取指定产品的对话历史，过滤掉 system 消息
    return await AiService(db).get_history(current_user.id, product_id)


@router.delete(
    "/conversation/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除对话记录",
    description="删除指定产品的对话记录，用于重置 AI 导购。",
)
async def delete_conversation(
    product_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    # 删除指定产品的对话记录，用于重置 AI 导购
    await AiService(db).delete_conversation(current_user.id, product_id)
