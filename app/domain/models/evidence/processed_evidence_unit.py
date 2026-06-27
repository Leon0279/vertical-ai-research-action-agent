"""Domain model for processed evidence units."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EvidenceType = Literal[
    "direct_fact",
    "supporting_signal",
    "comparison_signal",
    "status_signal",
    "background_signal",
]


class ProcessedEvidenceUnit(BaseModel):
    """Source-grounded evidence signal produced from candidate materials."""

    evidence_unit_id: str = Field(description="Stable identifier within this processing result.")
    source_ref: str = Field(description="Source reference backing this evidence unit.")
    source_family: str = Field(description="Source family the material came from.")
    source_type: str = Field(description="Source type the material came from.")
    content: str = Field(min_length=1, description="Task-aware evidence content.")
    evidence_type: EvidenceType = Field(description="Typed evidence signal category.")
    support_refs: list[str] = Field(
        default_factory=list,
        description="Minimal source refs supporting this evidence unit.",
    )
    target_problem: str | None = Field(
        default=None,
        description="Retrieval target problem this evidence supports.",
    )
    target_scope: dict[str, Any] | None = Field(
        default=None,
        description="Optional target scope carried from retrieval context.",
    )
    evidence_goal: str | None = Field(
        default=None,
        description="Optional evidence goal carried from retrieval context.",
    )
    sub_question: str | None = Field(
        default=None,
        description="Optional sub-question label carried from retrieval context.",
    )
    comparison_candidate: str | None = Field(
        default=None,
        description="Optional comparison candidate label carried from retrieval context.",
    )
    gap: str | None = Field(
        default=None,
        description="Optional information gap label carried from retrieval context.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional processing and source metadata.",
    )
