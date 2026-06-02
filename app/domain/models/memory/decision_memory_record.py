"""Domain model for one decision_memory row."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DecisionMemoryRecord(BaseModel):
    """Typed decision memory record aligned with the LLD table schema."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(
        min_length=1,
        description="Primary identifier for one durable decision memory record.",
    )
    user_id: str = Field(
        min_length=1,
        description="User ownership boundary for this project-scoped decision memory.",
    )
    project_id: str = Field(
        min_length=1,
        description="Stable logical project identifier under which this decision belongs.",
    )
    decision_title: str | None = Field(
        default=None,
        description="Short title of the decision.",
    )
    decision_question: str | None = Field(
        default=None,
        description="Question or problem this decision aims to resolve.",
    )
    chosen_option: str | None = Field(
        default=None,
        description="Final chosen option for the decision.",
    )
    alternatives: list[str] = Field(
        default_factory=list,
        description="Alternative options considered for the decision.",
    )
    rationale: str | None = Field(
        default=None,
        description="Reasoning or rationale supporting the decision.",
    )
    tradeoffs: list[str] = Field(
        default_factory=list,
        description="Key trade-offs associated with the decision.",
    )
    decision_state: str | None = Field(
        default=None,
        description=(
            "Domain-specific business state of the decision, such as proposed, "
            "accepted, reconsidering, or rejected."
        ),
    )
    record_status: str = Field(
        min_length=1,
        description=(
            "Lifecycle status of this memory record, such as active, superseded, "
            "archived, or pruned."
        ),
    )
    impact_scope: str | None = Field(
        default=None,
        description="Scope of impact for this decision.",
    )
    confidence: float | None = Field(
        default=None,
        description="Confidence score for the current decision record.",
    )
    decided_at: datetime | None = Field(
        default=None,
        description="Timestamp when the decision was formed, if known.",
    )
    supersedes_decision_id: str | None = Field(
        default=None,
        description="Optional older decision record superseded by this decision.",
    )
    superseded_by_decision_id: str | None = Field(
        default=None,
        description="Optional newer decision record that superseded this decision.",
    )
    embedding_text: str | None = Field(
        default=None,
        description=(
            "Embedding input text used for same-type similarity-assisted candidate resolution."
        ),
    )
    embedding_model: str | None = Field(
        default=None,
        description="Embedding model used to generate the associated embedding representation.",
    )
    embedding_version: str | None = Field(
        default=None,
        description="Version of the embedding model or embedding generation configuration.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Timestamp when this decision memory record was created.",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp when this decision memory record was last updated.",
    )
    derived_from_session_id: str | None = Field(
        default=None,
        description="Optional source session identifier from which this record was distilled.",
    )
    derived_from_run_id: str | None = Field(
        default=None,
        description="Optional source run identifier from which this record was distilled.",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        description="Optional supporting source references for this decision record.",
    )
