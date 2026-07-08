"""Domain model for family selection requests."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import ActionMode
from app.domain.models.tool_execution_layer.evidence_shape import EvidenceShape


class FamilySelectionRequest(BaseModel):
    """Input used to choose a retrieval family without selecting a concrete tool."""

    target_problem: str = Field(
        description="Current retrieval target problem or evidence need.",
    )
    action_mode: ActionMode = Field(
        default=ActionMode.EXTERNAL_ACQUISITION,
        description="High-level acquisition mode used to scope candidate families.",
    )
    evidence_goal: str | None = Field(
        default=None,
        description="Optional evidence acquisition goal, such as establish_coverage.",
    )
    evidence_shape: EvidenceShape | None = Field(
        default=None,
        description="Optional evidence shape hints used for family ranking.",
    )
    task_type: str | None = Field(
        default=None,
        description="Optional interpreted task type from upstream planning.",
    )
    task_framing: str | None = Field(
        default=None,
        description="Optional task framing signal from upstream planning.",
    )
    evidence_strategy: str | None = Field(
        default=None,
        description="Optional workflow evidence strategy from upstream routing.",
    )
    allowed_source_families: list[str] = Field(
        default_factory=list,
        description="Optional allow-list of source families for this acquisition.",
    )
    preferred_source_families: list[str] = Field(
        default_factory=list,
        description="Optional preference-ordered source families.",
    )
    blocked_source_families: list[str] = Field(
        default_factory=list,
        description="Source families that must not be selected.",
    )
    available_families: list[str] = Field(
        default_factory=list,
        description="Families available to the current runtime context.",
    )
