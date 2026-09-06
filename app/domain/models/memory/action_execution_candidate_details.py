"""Typed details proposed for action/execution memory."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ActionExecutionCandidateDetails(BaseModel):
    """LLM-supported business fields for an action candidate."""

    model_config = ConfigDict(extra="forbid")

    action_title: str | None = None
    action_description: str | None = None
    action_status: Literal[
        "todo",
        "in_progress",
        "blocked",
        "done",
        "cancelled",
    ] | None = None
    priority: str | None = None
    owner: str | None = None
    due_at: datetime | None = None
    blocking_reason: str | None = None
    result_summary: str | None = None
    completed_at: datetime | None = None
