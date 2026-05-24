"""Final structured output model returned by orchestration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums.task_type import TaskType
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models.action_item import ActionItem
from app.domain.models.citation import Citation


class StructuredOutput(BaseModel):
    """Final user-facing result in domain representation."""

    trace_id: str | None = None
    task_type: TaskType
    workflow_pattern: WorkflowPattern
    summary: str
    recommendation: str | None = None
    action_items: list[ActionItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float | None = None
    stage_history: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
