"""Paginated conversation message query result."""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.conversation.conversation_message import ConversationMessage


class ConversationMessagePage(BaseModel):
    """表示一个 session 的一页历史对话消息。"""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1,
        description="必填字段。当前消息页所属的稳定会话标识。",
    )
    messages: list[ConversationMessage] = Field(
        default_factory=list,
        description="可选字段。按创建时间从旧到新排列的本页消息。",
    )
    next_cursor: str | None = Field(
        default=None,
        description="可选字段。继续读取更早消息的 opaque cursor；没有更早消息时为 None。",
    )
