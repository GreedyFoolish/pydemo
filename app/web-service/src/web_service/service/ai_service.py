from collections.abc import AsyncGenerator
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from web_service.exception.ai import AiException
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


class AiService(BaseService):

    async def _load_product(self, product_id: int) -> Product:
        # 使用 selectinload 预加载关联数据，避免 N+1 查询问题
        result = await self.session.execute(
            select(Product)
            .options(selectinload(Product.categories), selectinload(Product.skus))
            .where(Product.id == product_id)
        )
        return result.unique().scalar_one()

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

    async def initialize(
        self, user_id: int, product_id: int
    ) -> AsyncGenerator[str, None]:
        # 初始化 AI 导购：生成产品介绍系统提示词，流式返回 AI 响应
        # 若已有对话记录（>1 条消息）则拒绝初始化，防止覆盖历史
        conv = await self._get_conversation(user_id, product_id)

        if conv is not None and len(conv.messages) > 1:
            raise AiException(message="该产品已有对话历史记录，请先清空后再初始化")

        product = await self._load_product(product_id)
        system_prompt = self._render_system_prompt(product)

        config = await self._get_required_ai_config()
        ai_chat = AIChat(config)
        # 提交并关闭会话，释放数据库连接回连接池，避免长时间占用
        await self.session.commit()
        await self.session.close()

        full_response = ""
        async for chunk in ai_chat.chat_stream(
            [AIMessage(role=MessageRole.SYSTEM, content=system_prompt)]
        ):
            full_response += chunk
            yield chunk

        # 流式响应完成后，创建或更新对话记录
        if conv is None:
            conv = AiConversation(
                user_id=user_id,
                product_id=product_id,
                messages=[
                    {"role": MESSAGE_ROLE_SYSTEM, "content": system_prompt},
                    {"role": MESSAGE_ROLE_ASSISTANT, "content": full_response},
                ],
            )
            self.session.add(conv)
        else:
            # 已有空对话记录，更新消息内容
            conv.messages = [
                {"role": MESSAGE_ROLE_SYSTEM, "content": system_prompt},
                {"role": MESSAGE_ROLE_ASSISTANT, "content": full_response},
            ]
            # merge: 会话关闭后 conv 变为游离状态，merge 将其重新关联到当前会话
            conv = await self.session.merge(conv)

        await self.session.flush()

    async def send_message_stream(
        self, user_id: int, product_id: int, content: str
    ) -> AsyncGenerator[str, None]:
        # 发送用户消息并流式返回 AI 响应，自动追加到对话历史
        conv = await self._get_conversation(user_id, product_id)
        if conv is None:
            raise AiException(message="未找到对话记录，请先初始化AI导购")

        ai_messages = [
            AIMessage(role=MessageRole(m["role"]), content=m["content"])
            for m in conv.messages
        ]
        ai_messages.append(AIMessage(role=MessageRole.USER, content=content))

        config = await self._get_required_ai_config()
        ai_chat = AIChat(config)
        # 提交并关闭会话，释放数据库连接回连接池
        await self.session.commit()
        await self.session.close()

        full_response = ""
        async for chunk in ai_chat.chat_stream(ai_messages):
            full_response += chunk
            yield chunk

        # 将用户消息和 AI 响应追加到对话记录
        conv.messages = [
            *conv.messages,
            {"role": MESSAGE_ROLE_USER, "content": content},
            {"role": MESSAGE_ROLE_ASSISTANT, "content": full_response},
        ]
        # merge: 会话关闭后 conv 变为游离状态，merge 将其重新关联到当前会话
        conv = await self.session.merge(conv)
        await self.session.flush()

    async def delete_conversation(self, user_id: int, product_id: int) -> None:
        conv = await self._get_conversation(user_id, product_id)
        if conv is not None:
            await self.session.delete(conv)
            await self.session.flush()
