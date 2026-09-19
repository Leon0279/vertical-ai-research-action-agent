"""Public response schema for one compressed Session Memory turn."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionTurnSummaryResponse(BaseModel):
    """Expose a compressed turn summary, never the original message body."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    role: str = Field(min_length=1)
    content_summary: str = Field(min_length=1)
    created_at: datetime | None = None
