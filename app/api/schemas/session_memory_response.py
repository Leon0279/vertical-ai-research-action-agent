"""Public Session Memory query response."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.session_turn_summary_response import SessionTurnSummaryResponse


class SessionMemoryResponse(BaseModel):
    """Expose compact continuity state without ownership or scratchpad internals."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    session_id: str = Field(min_length=1)
    session_working_summary: str | None = None
    recent_turn_summaries: list[SessionTurnSummaryResponse] = Field(
        default_factory=list
    )
    latest_recommendation: str | None = None
    latest_action_items: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    current_local_task_framing: str | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None
