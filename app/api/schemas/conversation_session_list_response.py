"""Paginated conversation session list response schema."""

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.conversation_session_summary_response import (
    ConversationSessionSummaryResponse,
)


class ConversationSessionListResponse(BaseModel):
    """返回指定用户的一页可回看 conversation sessions。"""

    model_config = ConfigDict(extra="forbid")

    sessions: list[ConversationSessionSummaryResponse] = Field(
        default_factory=list,
        description="可选字段。按最近更新时间从新到旧排列的会话。",
    )
    next_cursor: str | None = Field(default=None, description="可选字段。继续读取更早会话的 opaque cursor。")
