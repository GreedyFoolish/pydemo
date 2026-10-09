from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from openai import OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from web_service.exception.ai import AiException
from web_service.exception.base import BusinessException, ErrorCode
from web_service.model.ai_conversation import AiConversation
from web_service.model.product import Product
from web_service.model.setting_item import SettingItem
from web_service.service.base import BaseService
from web_utils.ai.chat import AIChat, AIChatConfig, AIMessage, MessageRole

# 消息角色常量，用于对话消息的序列化/反序列化，与 MessageRole 枚举保持同步
MESSAGE_ROLE_SYSTEM = "system"
MESSAGE_ROLE_USER = "user"
MESSAGE_ROLE_ASSISTANT = "assistant"

_template_dir = Path(__file__).parent / "template"
_jinja_env = Environment(loader=FileSystemLoader(str(_template_dir)))


@dataclass
class InitReadResult:
    """initialize 读阶段结果：session 关闭前将所有 ORM 数据转为纯 Python 对象。"""

    product_id: int
    user_id: int
    system_prompt: str
    ai_config: AIChatConfig
    has_history: bool  # True 表示已有对话记录，需要 update 而非 insert


@dataclass
class MessageReadResult:
    """send_message 读阶段结果：会话关闭前将消息历史和 AI 配置转为纯 Python 对象。"""

    product_id: int
    user_id: int
    ai_messages: list[AIMessage]
    ai_config: AIChatConfig


class AiService(BaseService):

    async def _load_product(self, product_id: int) -> Product:
        # 使用 selectinload 预加载关联数据，避免 N+1 查询问题
        result = await self.session.execute(
            select(Product)
            .options(selectinload(Product.categories), selectinload(Product.skus))
            .where(Product.id == product_id)
        )
        product = result.unique().scalar_one_or_none()
        if product is None:
            raise BusinessException(
                error_code=ErrorCode.NOT_FOUND,
                message="产品不存在",
                detail=f"model=Product, id={product_id}",
            )
        return product

    def _render_system_prompt(self, product: Product) -> str:
        template = _jinja_env.get_template("product_intro.j2")
        categories_str = "、".join(c.name for c in product.categories) or None
        skus = [
            {"sku_code": s.sku_code, "price": str(s.price), "stock": s.stock}
            for s in product.skus
        ]
        return template.render(
            product={
                "name": product.name,
                "brand": product.brand,
                "description": product.description,
                "categories": categories_str,
                "skus": skus or None,
            }
        )

    async def _get_required_ai_config(self) -> AIChatConfig:
        # 从设置表读取 AI 服务必需的配置项，缺失时抛出异常引导用户联系管理员
        keys = ["ai_api_key", "ai_base_url", "ai_model"]
        result = await self.session.execute(
            select(SettingItem).where(SettingItem.key.in_(keys))
        )
        settings_map = {s.key: s.value for s in result.scalars().all()}

        missing = [k for k in keys if not settings_map.get(k)]
        if missing:
            raise AiException(
                message="AI服务配置不完整，请联系管理员",
                detail=f"缺少以下配置项：{', '.join(missing)}",
            )

        return AIChatConfig(
            api_key=settings_map["ai_api_key"],
            base_url=settings_map["ai_base_url"],
            model=settings_map["ai_model"],
        )

    async def _get_conversation(
        self, user_id: int, product_id: int
    ) -> AiConversation | None:
        result = await self.session.execute(
            select(AiConversation).where(
                AiConversation.user_id == user_id,
                AiConversation.product_id == product_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_history(self, user_id: int, product_id: int) -> list[dict]:
        # 返回对话历史，过滤掉 system 消息（仅用于 AI 上下文，不展示给用户）
        conv = await self._get_conversation(user_id, product_id)
        if conv is None:
            return []
        return [m for m in conv.messages if m["role"] != MESSAGE_ROLE_SYSTEM]

    async def read_initialize(self, user_id: int, product_id: int) -> InitReadResult:
        # 读阶段：加载产品、渲染提示词、读取 AI 配置，session 关闭前将 ORM 数据转为纯 Python 对象
        conv = await self._get_conversation(user_id, product_id)
        if conv is not None and len(conv.messages) > 1:
            raise AiException(message="该产品已有对话历史记录，请先清空后再初始化")

        product = await self._load_product(product_id)
        system_prompt = self._render_system_prompt(product)
        config = await self._get_required_ai_config()

        return InitReadResult(
            product_id=product_id,
            user_id=user_id,
            system_prompt=system_prompt,
            ai_config=config,
            has_history=conv is not None,
        )

    async def initialize_stream(
        self, read_result: InitReadResult
    ) -> AsyncGenerator[str, None]:
        # 流式阶段：不依赖数据库连接，纯 AI 调用
        ai_chat = AIChat(read_result.ai_config)
        full_response = ""
        try:
            # 调用 AI 流式接口：必须包含至少一条 user 消息（部分 API 不接受纯 system 请求）
            # 智谱 BigModel（glm-5.2）不允许 messages 数组只有`system` 或`assistant` 消息 ，至少要有一条`user` 消息。
            # 这就是错误码`1214 / messages 参数非法` 的原因。OpenAI 对此比较宽松不会报错，但 BigModel 严格校验。
            # system 消息携带产品上下文，user 消息触发 AI 生成产品介绍
            async for chunk in ai_chat.chat_stream(
                [
                    AIMessage(
                        role=MessageRole.SYSTEM, content=read_result.system_prompt
                    ),
                    AIMessage(
                        role=MessageRole.USER, content="你好，请介绍一下这个产品"
                    ),
                ]
            ):
                # 累积完整回复，用于后续持久化到对话记录
                full_response += chunk
                # 实时推送给 WebSocket 客户端
                yield chunk
        except OpenAIError as e:
            # 将 OpenAI 底层异常包装为业务异常，由 API 层统一处理并返回给客户端
            raise AiException(
                message="AI 服务调用失败",
                detail=f"{type(e).__name__}: {e}",
                original_error=e,
            ) from e

    async def write_initialize(
        self, read_result: InitReadResult, full_response: str
    ) -> None:
        # 写阶段：用新 session 将 AI 响应持久化到对话记录
        if not read_result.has_history:
            conv = AiConversation(
                product_id=read_result.product_id,
                user_id=read_result.user_id,
                messages=[
                    {"role": MESSAGE_ROLE_SYSTEM, "content": read_result.system_prompt},
                    {"role": MESSAGE_ROLE_ASSISTANT, "content": full_response},
                ],
            )
            self.session.add(conv)
        else:
            conv = await self._get_conversation(
                read_result.user_id, read_result.product_id
            )
            conv.messages = [
                {"role": MESSAGE_ROLE_SYSTEM, "content": read_result.system_prompt},
                {"role": MESSAGE_ROLE_ASSISTANT, "content": full_response},
            ]
        await self.session.flush()

    async def read_message(
        self, user_id: int, product_id: int, content: str
    ) -> MessageReadResult:
        # 读阶段：加载对话历史并转为纯 Python 对象，session 关闭后仍可安全使用
        conv = await self._get_conversation(user_id, product_id)
        if conv is None:
            raise AiException(message="未找到对话记录，请先初始化AI导购")

        ai_messages = [
            AIMessage(role=MessageRole(m["role"]), content=m["content"])
            for m in conv.messages
        ]
        ai_messages.append(AIMessage(role=MessageRole.USER, content=content))

        config = await self._get_required_ai_config()

        return MessageReadResult(
            product_id=product_id,
            user_id=user_id,
            ai_messages=ai_messages,
            ai_config=config,
        )

    async def send_message_stream(
        self, read_result: MessageReadResult
    ) -> AsyncGenerator[str, None]:
        # 流式阶段：不依赖数据库连接，纯 AI 调用
        ai_chat = AIChat(read_result.ai_config)
        full_response = ""
        try:
            async for chunk in ai_chat.chat_stream(read_result.ai_messages):
                full_response += chunk
                yield chunk
        except OpenAIError as e:
            # 将 OpenAI 底层异常包装为业务异常，由 API 层统一处理并返回给客户端
            raise AiException(
                message="AI 服务调用失败",
                detail=f"{type(e).__name__}: {e}",
                original_error=e,
            ) from e

    async def write_message(
        self, read_result: MessageReadResult, content: str, full_response: str
    ) -> None:
        # 写阶段：用新 session 将用户消息和 AI 响应追加到对话记录
        conv = await self._get_conversation(read_result.user_id, read_result.product_id)
        conv.messages = [
            *conv.messages,
            {"role": MESSAGE_ROLE_USER, "content": content},
            {"role": MESSAGE_ROLE_ASSISTANT, "content": full_response},
        ]
        await self.session.flush()

    async def delete_conversation(self, user_id: int, product_id: int) -> None:
        conv = await self._get_conversation(user_id, product_id)
        if conv is not None:
            await self.session.delete(conv)
            await self.session.flush()
