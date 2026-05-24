"""API schema for action items."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ActionItemSchema(BaseModel):
    """User-facing action item structure."""

    title: str
    description: str | None = None
    priority: str = "medium"
    metadata: dict[str, Any] = Field(default_factory=dict)

