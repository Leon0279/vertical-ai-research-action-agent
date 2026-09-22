"""Paginated conversation message response schema."""

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.conversation_message_response import ConversationMessageResponse


class ConversationMessageListResponse(BaseModel):
    """返回一个 session 的一页历史对话消息。"""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, description="必填字段。本页消息所属会话标识。")
    messages: list[ConversationMessageResponse] = Field(
        default_factory=list,
        description="可选字段。按创建时间从旧到新排列的本页消息。",
    )
    next_cursor: str | None = Field(
        default=None,
        description="可选字段。继续读取更早消息的 opaque cursor。",
    )
