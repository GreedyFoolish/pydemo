"""AI 导购相关的 DTO 定义。

对应模型：web_service.model.ai_conversation.AiConversation
用于 AI 对话的消息格式定义和接口请求/响应体。
"""

from datetime import datetime
from pydantic import ConfigDict, Field
from web_service.schema.base import BaseSchema


class AiMessageItem(BaseSchema):
    """单条对话消息。"""

    role: str = Field(description="消息角色：system/user/assistant")
    content: str = Field(description="消息内容")


class AiSendMessageRequest(BaseSchema):
    """发送消息的请求体。"""

    product_id: int = Field(description="产品ID")
    content: str = Field(description="用户发送的消息内容")


class AiConversationResponse(BaseSchema):
    """对话记录的完整响应体。"""

    user_id: int = Field(description="用户ID")
    product_id: int = Field(description="产品ID")
    messages: list[AiMessageItem] = Field(default_factory=list, description="消息列表")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = ConfigDict(from_attributes=True)
