"""Response schemas for agent API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.action_item_schema import ActionItemSchema
from app.api.schemas.citation_schema import CitationSchema


class AgentRunResponse(BaseModel):
    """Single-entry response payload for the run endpoint."""

    trace_id: str | None = Field(default=None, description="Request trace identifier.")
    task_type: str
    workflow_pattern: str
    summary: str
    recommendation: str | None = None
    action_items: list[ActionItemSchema] = Field(default_factory=list)
    citations: list[CitationSchema] = Field(default_factory=list)
    confidence: float | None = None
    stage_history: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
