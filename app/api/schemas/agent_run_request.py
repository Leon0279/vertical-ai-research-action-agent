"""Request schemas for agent API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    """Single-entry request payload for the run endpoint."""

    query: str = Field(..., min_length=1, description="User input query.")
    session_id: str | None = Field(default=None, description="Session identifier.")
    project_id: str | None = Field(default=None, description="Project identifier.")
    constraints: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)

