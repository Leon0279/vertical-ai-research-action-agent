"""Public conversation message projection used by history queries."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ConversationContentFormat, ConversationMessageRole
from app.domain.models.conversation.conversation_assistant_details import (
    ConversationAssistantDetails,
)


class ConversationMessage(BaseModel):
    """表示历史查询返回的一条用户可见对话消息。"""

    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(
        min_length=1,
        description="必填字段。用于前端稳定标识单条历史消息的唯一标识。",
    )
    role: ConversationMessageRole = Field(
        description="必填字段。消息发送方角色，例如 user 或 assistant。",
    )
    content: str = Field(
        min_length=1,
        description="必填字段。向用户展示的消息正文。",
    )
    content_format: ConversationContentFormat = Field(
        description="必填字段。消息正文采用的 text、markdown 或 JSON 格式。",
    )
    created_at: datetime = Field(
        description="必填字段。消息创建时间，用于还原会话内的时间顺序。",
    )
    parent_message_id: str | None = Field(
        default=None,
        description="可选字段。父消息标识；当前通常由 assistant 消息指向触发它的 user 消息。",
    )
    assistant_details: ConversationAssistantDetails | None = Field(
        default=None,
        description="可选字段。assistant 消息的用户可见结构化信息；其它角色或旧数据无法解析时为 None。",
    )
