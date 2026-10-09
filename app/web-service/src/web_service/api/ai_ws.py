"""
AI 导购 WebSocket 接口。

提供双向实时通信，客户端通过 WebSocket 发送指令，服务端流式推送 AI 响应。

连接地址：ws://host/ws/ai/{product_id}?token={jwt_token}

客户端消息格式（JSON）：
- 初始化对话：{"action": "initialize"}
- 发送消息：{"action": "send_message", "content": "用户问题"}

服务端响应格式（JSON）：
- 流式数据块：{"type": "chunk", "content": "..."}
- 完成标记：{"type": "done"}
- 错误信息：{"type": "error", "message": "...", "detail": "..."}

注意：WebSocket 无法使用 HTTP Header 认证，通过 URL 参数传递 token。
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from web_service.core.auth import get_user_from_token
from web_service.core.database import get_session_factory, run_in_session
from web_service.exception import BusinessException, AiException, AuthException
from web_service.service.ai_service import AiService

router = APIRouter()

# 首包超时：AI API 必须在此时间内返回第一个 chunk，否则视为无响应
_FIRST_CHUNK_TIMEOUT = 60
# 包间超时：流式期间连续两个 chunk 之间的最大间隔，超时视为中途卡住
_INTER_CHUNK_TIMEOUT = 15
# 整体超时：三段式流程的兜底保护（主要防读/写阶段 DB 挂起）
_OVERALL_TIMEOUT = 120


async def _stream_with_timeout(
    stream: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """为异步生成器添加首包超时和包间超时保护。

    第一个 chunk 使用较短的首包超时（API 无响应时快速失败），
    后续 chunk 使用包间超时（允许正常长度的回答，但检测中途卡死）。

    超时时抛出 AiException 而非 TimeoutError，
    因为 Python 3.11+ 中 asyncio.TimeoutError 就是内置 TimeoutError，
    抛 TimeoutError 会被外层 except asyncio.TimeoutError 误捕获，导致错误信息不准确。
    """
    is_first = True
    try:
        while True:
            timeout = _FIRST_CHUNK_TIMEOUT if is_first else _INTER_CHUNK_TIMEOUT
            try:
                chunk = await asyncio.wait_for(stream.__anext__(), timeout=timeout)
            except asyncio.TimeoutError as e:
                if is_first:
                    raise AiException(
                        message="AI 服务无响应，请稍后重试", original_error=e
                    ) from e
                raise AiException(
                    message="AI 服务响应中断，请稍后重试", original_error=e
                ) from e
            is_first = False
            yield chunk
    except StopAsyncIteration:
        pass


async def _handle_initialize(
    websocket: WebSocket, user_id: int, product_id: int
) -> None:
    """三段式处理 initialize：读→流式AI→写，每段独立 session。"""
    # 读阶段：加载数据后立即关闭 session，释放连接回池
    read_result = await run_in_session(
        lambda db: AiService(db).read_initialize(user_id, product_id)
    )

    # 流式阶段：不占用数据库连接，纯 AI 调用，带首包/包间超时保护
    full_response = ""

    async def _stream(db):
        nonlocal full_response
        svc = AiService(db)
        async for chunk in _stream_with_timeout(svc.initialize_stream(read_result)):
            await websocket.send_json({"type": "chunk", "content": chunk})
            full_response += chunk
        await websocket.send_json({"type": "done"})

    await run_in_session(_stream)

    # 写阶段：用新 session 持久化结果
    async def _write(db):
        svc = AiService(db)
        await svc.write_initialize(read_result, full_response)
        await db.commit()

    await run_in_session(_write)


async def _handle_send_message(
    websocket: WebSocket, user_id: int, product_id: int, content: str
) -> None:
    """三段式处理 send_message：读→流式AI→写，每段独立 session。"""
    # 读阶段
    read_result = await run_in_session(
        lambda db: AiService(db).read_message(user_id, product_id, content)
    )

    # 流式阶段：带首包/包间超时保护
    full_response = ""

    async def _stream(db):
        nonlocal full_response
        svc = AiService(db)
        async for chunk in _stream_with_timeout(svc.send_message_stream(read_result)):
            await websocket.send_json({"type": "chunk", "content": chunk})
            full_response += chunk
        await websocket.send_json({"type": "done"})

    await run_in_session(_stream)

    # 写阶段
    async def _write(db):
        svc = AiService(db)
        await svc.write_message(read_result, content, full_response)
        await db.commit()

    await run_in_session(_write)


@router.websocket("/{product_id}")
async def ai_websocket(
    websocket: WebSocket,
    product_id: int,
    token: str = Query(...),
):
    await websocket.accept()  # 协议升级：HTTP → WebSocket
    # WebSocket 无法使用 HTTP Header 认证，通过 URL 参数传递 token
    db = get_session_factory()()
    try:
        user = await get_user_from_token(token, db)
    except AuthException:
        await db.close()
        await websocket.close(code=1008, reason="认证失败")
        return
    await db.close()
    user_id = user.id

    try:
        # 持续监听客户端消息，根据 action 执行不同操作
        while True:
            # 阻塞等待客户端发送一条文本消息（WebSocket 双向通信的接收端）
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # 客户端发送了非 JSON 内容，返回错误但不断开连接，继续监听下一条
                await websocket.send_json(
                    {"type": "error", "message": "无效的JSON格式"}
                )
                continue

            action = data.get("action")

            if action == "initialize":
                try:
                    # 整体超时保护：兜底防读/写阶段 DB 挂起，流式阶段由首包/包间超时控制
                    await asyncio.wait_for(
                        _handle_initialize(websocket, user_id, product_id),
                        timeout=_OVERALL_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    await websocket.send_json(
                        {"type": "error", "message": "AI 服务响应超时，请稍后重试"}
                    )
                except BusinessException as e:
                    await websocket.send_json(
                        {"type": "error", "message": e.message, "detail": e.detail}
                    )
                except Exception as e:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"服务内部错误: {type(e).__name__}",
                        }
                    )

            elif action == "send_message":
                # 发送消息：校验内容非空后流式返回 AI 响应
                content = data.get("content", "").strip()
                if not content:
                    await websocket.send_json(
                        {"type": "error", "message": "消息内容不能为空"}
                    )
                    continue

                try:
                    await asyncio.wait_for(
                        _handle_send_message(websocket, user_id, product_id, content),
                        timeout=_OVERALL_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    await websocket.send_json(
                        {"type": "error", "message": "AI 服务响应超时，请稍后重试"}
                    )
                except BusinessException as e:
                    await websocket.send_json(
                        {"type": "error", "message": e.message, "detail": e.detail}
                    )
                except Exception as e:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"服务内部错误: {type(e).__name__}",
                        }
                    )

            else:
                await websocket.send_json(
                    {"type": "error", "message": f"未知操作: {action}"}
                )

    except WebSocketDisconnect:
        # 客户端断开连接，正常退出
        pass
