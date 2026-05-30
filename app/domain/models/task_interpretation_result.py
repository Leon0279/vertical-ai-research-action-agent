"""Structured result produced by task interpretation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums.task_type import TaskType


class TaskInterpretationResult(BaseModel):
    """Initial semantic interpretation of a normalized user request."""

    model_config = ConfigDict(extra="forbid")

    user_goal: str = Field(min_length=1)
    task_type: TaskType
    task_framing: str | None = None
    constraints: list[str] = Field(default_factory=list)
    project_context_summary: str | None = None

    @field_validator("user_goal", "task_framing", "project_context_summary", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("constraints", mode="before")
    @classmethod
    def _strip_constraints(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
