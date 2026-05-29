"""Runtime capabilities and execution boundaries for a request run."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuntimeContext(BaseModel):
    """Runtime capabilities and execution boundaries for a request run."""

    request_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    session_id_generated: bool = False
    stage_history: list[str] = Field(default_factory=list)

    available_tools: list[str] = Field(default_factory=list)
    tool_registry_version: str | None = None
    latency_budget_ms: int | None = None
    iteration_budget: int | None = None
    scope_restrictions: list[str] = Field(default_factory=list)
    environment_flags: list[str] = Field(default_factory=list)
