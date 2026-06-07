"""Partitioned supporting context available to the current run."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models.context.context_item import ContextItem


class SupplementalContext(BaseModel):
    """Partitioned supporting context available to the current run."""

    session_support: list[ContextItem] = Field(default_factory=list)
    project_support: list[ContextItem] = Field(default_factory=list)
    decision_support: list[ContextItem] = Field(default_factory=list)
    action_support: list[ContextItem] = Field(default_factory=list)
    policy_support: list[ContextItem] = Field(default_factory=list)
    research_support: list[ContextItem] = Field(default_factory=list)
    external_evidence_support: list[ContextItem] = Field(default_factory=list)
