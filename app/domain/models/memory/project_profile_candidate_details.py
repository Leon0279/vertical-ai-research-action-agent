"""Typed details proposed for project profile memory."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProjectProfileCandidateDetails(BaseModel):
    """LLM-supported business fields for a project profile candidate."""

    model_config = ConfigDict(extra="forbid")

    project_name: str | None = None
    project_goal: str | None = None
    project_background: str | None = None
    domain: str | None = None
    current_stage: str | None = None
    constraints: list[str] = Field(default_factory=list)
    important_context: str | None = None
