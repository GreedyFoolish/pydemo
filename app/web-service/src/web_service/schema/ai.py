from datetime import datetime
from pydantic import ConfigDict
from web_service.schema.base import BaseSchema


class AiMessageItem(BaseSchema):
    role: str
    content: str


class AiConversationResponse(BaseSchema):
    user_id: int
    product_id: int
    messages: list[AiMessageItem] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
