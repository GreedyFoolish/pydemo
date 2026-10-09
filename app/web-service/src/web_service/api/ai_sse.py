"""
AI 导购 SSE (Server-Sent Events) 流式接口。

客户端通过 EventSource 接收服务端推送的文本流：
- GET  /initialize/{product_id}    初始化对话，流式返回产品介绍
- POST /message                    发送消息，流式返回 AI 响应

SSE 数据格式：
- 正常数据：data: {content}\\n\\n
- 错误事件：event: error\\ndata: {message}\\n\\n
"""

from typing import Annotated
from fastapi import APIRouter, Depends, Request
from loguru import logger
from starlette.responses import StreamingResponse
from web_service.core.auth import get_current_user
from web_service.core.database import get_session_factory, run_in_session
from web_service.exception.base import BusinessException
from web_service.model.user import User
from web_service.schema.ai import AiSendMessageRequest
from web_service.service.ai_service import AiService

router = APIRouter(prefix="/api/ai/sse", tags=["AI SSE"])


@router.get(
    "/initialize/{product_id}",
    summary="初始化对话（SSE）",
    description="初始化 AI 导购对话，流式返回产品介绍。",
)
async def initialize_conversation(
    request: Request,
    product_id: int,
    user: Annotated[User, Depends(get_current_user)],
):
    request.state.is_stream = True

    async def event_stream():
        # 读阶段也放在 generator 内部，异常才能被 try/except 捕获转为 SSE error 事件
        try:
            read_result = await run_in_session(
                lambda db: AiService(db).read_initialize(user.id, product_id)
            )
        except BusinessException as e:
            logger.warning(f"SSE initialize 读阶段业务异常: {e.message}")
            yield f"event: error\ndata: {e.message}\n\n"
            return
        except Exception as e:
            logger.exception(f"SSE initialize 读阶段未知异常: {type(e).__name__}: {e}")
            yield f"event: error\ndata: {type(e).__name__}: {e}\n\n"
            return

        # 流式阶段
        full_response = ""
        db = get_session_factory()()
        try:
            svc = AiService(db)
            async for chunk in svc.initialize_stream(read_result):
                full_response += chunk
                yield f"data: {chunk}\n\n"
        except BusinessException as e:
            logger.warning(f"SSE initialize 业务异常: {e.message}")
            yield f"event: error\ndata: {e.message}\n\n"
            return
        except Exception as e:
            logger.exception(f"SSE initialize 未知异常: {type(e).__name__}: {e}")
            yield f"event: error\ndata: {type(e).__name__}: {e}\n\n"
            return
        finally:
            await db.close()

        # 写阶段：用新 session 持久化结果
        async def _write(db):
            svc = AiService(db)
            await svc.write_initialize(read_result, full_response)
            await db.commit()

        try:
            await run_in_session(_write)
        except Exception:
            logger.exception("SSE initialize 写阶段失败")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post(
    "/message",
    summary="发送消息（SSE）",
    description="发送用户消息，流式返回 AI 响应。",
)
async def send_message(
    request: Request,
    data: AiSendMessageRequest,
    user: Annotated[User, Depends(get_current_user)],
):
    request.state.is_stream = True

    async def event_stream():
        # 读阶段也放在 generator 内部，异常才能被 try/except 捕获转为 SSE error 事件
        try:
            read_result = await run_in_session(
                lambda db: AiService(db).read_message(
                    user.id, data.product_id, data.content
                )
            )
        except BusinessException as e:
            logger.warning(f"SSE message 读阶段业务异常: {e.message}")
            yield f"event: error\ndata: {e.message}\n\n"
            return
        except Exception as e:
            logger.exception(f"SSE message 读阶段未知异常: {type(e).__name__}: {e}")
            yield f"event: error\ndata: {type(e).__name__}: {e}\n\n"
            return

        # 流式阶段
        full_response = ""
        db = get_session_factory()()
        try:
            svc = AiService(db)
            async for chunk in svc.send_message_stream(read_result):
                full_response += chunk
                yield f"data: {chunk}\n\n"
        except BusinessException as e:
            logger.warning(f"SSE message 业务异常: {e.message}")
            yield f"event: error\ndata: {e.message}\n\n"
            return
        except Exception as e:
            logger.exception(f"SSE message 未知异常: {type(e).__name__}: {e}")
            yield f"event: error\ndata: {type(e).__name__}: {e}\n\n"
            return
        finally:
            await db.close()

        # 写阶段
        async def _write(db):
            svc = AiService(db)
            await svc.write_message(read_result, data.content, full_response)
            await db.commit()

        try:
            await run_in_session(_write)
        except Exception:
            logger.exception("SSE message 写阶段失败")

    return StreamingResponse(event_stream(), media_type="text/event-stream")
