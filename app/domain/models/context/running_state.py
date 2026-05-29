"""Canonical mutable state for a single request run."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunningState(BaseModel):
    """Canonical mutable state for a single request run."""

    original_query: str = Field(min_length=1)
    task_type: str | None = None
    user_goal: str | None = None
    task_framing: str | None = None
    constraints: list[str] = Field(default_factory=list)

    project_scope_id: str | None = None
    project_context_summary: str | None = None
    current_bottleneck_summary: str | None = None
    active_decision_summary: str | None = None
    current_action_status: str | None = None

    plan: list[str] = Field(default_factory=list)
    sub_questions: list[str] = Field(default_factory=list)
    comparison_candidates: list[str] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)

    retrieved_evidence_refs: list[str] = Field(default_factory=list)
    evidence_summary: str | None = None
    intermediate_findings: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    final_recommendation: str | None = None
    action_items: list[str] = Field(default_factory=list)
    confidence: str | None = None
