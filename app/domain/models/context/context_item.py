"""Supporting context item retained outside core running state."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextItem(BaseModel):
    """Selected supporting context retained outside core running state."""

    id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    scope_id: str | None = None
    summary: str = Field(min_length=1)
    priority: int
    freshness_tag: str | None = None
    confidence: str | None = None
    can_assimilate_to_state: bool = False
    usage_hint: str | None = None
