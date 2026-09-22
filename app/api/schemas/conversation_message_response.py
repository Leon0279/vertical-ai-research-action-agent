"""Public response schema for one conversation history message."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.conversation_assistant_details_response import (
    ConversationAssistantDetailsResponse,
)
from app.domain.enums import ConversationContentFormat, ConversationMessageRole


class ConversationMessageResponse(BaseModel):
    """返回一条可供前端还原历史对话的消息。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    message_id: str = Field(min_length=1, description="必填字段。消息的稳定唯一标识。")
    role: ConversationMessageRole = Field(description="必填字段。消息发送方角色。")
    content: str = Field(min_length=1, description="必填字段。向用户展示的消息正文。")
    content_format: ConversationContentFormat = Field(description="必填字段。消息正文格式。")
    created_at: datetime = Field(description="必填字段。消息创建时间。")
    parent_message_id: str | None = Field(default=None, description="可选字段。父消息标识。")
    assistant_details: ConversationAssistantDetailsResponse | None = Field(
        default=None,
        description="可选字段。assistant 消息的结构化展示信息；其它角色或不可解析旧数据为 None。",
    )
