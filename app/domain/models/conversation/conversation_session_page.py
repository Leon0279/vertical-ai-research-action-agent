"""Paginated conversation session query result."""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.conversation.conversation_session_summary import (
    ConversationSessionSummary,
)


class ConversationSessionPage(BaseModel):
    """表示指定用户的一页可回看 conversation sessions。"""

    model_config = ConfigDict(extra="forbid")

    sessions: list[ConversationSessionSummary] = Field(
        default_factory=list,
        description="可选字段。按最近更新时间从新到旧排列的本页会话。",
    )
    next_cursor: str | None = Field(
        default=None,
        description="可选字段。继续读取更早会话的 opaque cursor；没有下一页时为 None。",
    )
