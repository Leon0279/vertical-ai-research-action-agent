"""Request-scoped context model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RequestContext(BaseModel):
    """Transport-agnostic request context for orchestration."""

    original_query: str
    session_id: str | None = None
    project_id: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)

