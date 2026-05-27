"""Request-scoped context model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequestContext(BaseModel):
    """Transport-agnostic request context for orchestration."""

    original_query: str
    user_id: str = Field(min_length=1)
    session_id: str | None = None
    project_id: str | None = None
