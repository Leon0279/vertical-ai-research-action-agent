"""Domain model for one action_memory row."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ActionMemoryRecord(BaseModel):
    """Typed action memory record aligned with the LLD table schema."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(
        min_length=1,
        description="Primary identifier for one durable action memory record.",
    )
    user_id: str = Field(
        min_length=1,
        description="User ownership boundary for this project-scoped action memory.",
    )
    project_id: str = Field(
        min_length=1,
        description="Stable logical project identifier under which this action belongs.",
    )
    parent_decision_id: str | None = Field(
        default=None,
        description="Optional linked decision that this action originated from.",
    )
    action_title: str | None = Field(
        default=None,
        description="Short title of the action item.",
    )
    action_description: str | None = Field(
        default=None,
        description="Detailed description of the action item.",
    )
    action_status: str = Field(
        min_length=1,
        description=(
            "Domain-specific business state of the action, such as todo, "
            "in_progress, blocked, done, or cancelled."
        ),
    )
    priority: str | None = Field(
        default=None,
        description="Priority of the action item.",
    )
    owner: str | None = Field(
        default=None,
        description="Optional owner responsible for the action item.",
    )
    due_at: datetime | None = Field(
        default=None,
        description="Optional due date for the action item.",
    )
    blocking_reason: str | None = Field(
        default=None,
        description="Optional reason that the action is currently blocked.",
    )
    result_summary: str | None = Field(
        default=None,
        description="Optional summary of the outcome after the action completes.",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Timestamp when the action was completed, if known.",
    )
    record_status: str = Field(
        min_length=1,
        description=(
            "Lifecycle status of this memory record, such as active, archived, "
            "or pruned."
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="Confidence score for the current action record.",
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
        description="Timestamp when this action memory record was created.",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp when this action memory record was last updated.",
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
        description="Optional supporting source references for this action record.",
    )
