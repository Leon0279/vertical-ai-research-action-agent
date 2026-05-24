"""Request trace model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequestTrace(BaseModel):
    """Minimal request-level trace metadata."""

    trace_id: str
    task_type: str | None = None
    workflow_pattern: str | None = None
    planning_depth: str | None = None
    stage_history: list[str] = Field(default_factory=list)

