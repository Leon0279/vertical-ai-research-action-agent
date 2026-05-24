"""Domain model for session memory."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SessionMemory(BaseModel):
    """Thread/session short-term memory."""

    session_id: str | None = None
    message_history: list[str] = Field(default_factory=list)
    active_user_goal: str | None = None
    active_task_type: str | None = None
    task_framing: str | None = None
    session_project_context: dict[str, Any] = Field(default_factory=dict)
    session_constraints: dict[str, Any] = Field(default_factory=dict)
    latest_recommendation: str | None = None
    latest_action_items: list[str] = Field(default_factory=list)

