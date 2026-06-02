"""Domain model for one project_profile_memory row."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectProfileMemoryRecord(BaseModel):
    """Typed project profile memory record aligned with the LLD table schema."""

    model_config = ConfigDict(extra="forbid")

    project_profile_id: str = Field(
        min_length=1,
        description=(
            "Identifier for one specific version of a project profile record, "
            "rather than the logical project itself."
        ),
    )
    project_id: str = Field(
        min_length=1,
        description=(
            "Stable logical project identifier shared across multiple versions "
            "of project profile records for the same project."
        ),
    )
    user_id: str = Field(
        min_length=1,
        description="User ownership boundary for this project-scoped long-term memory.",
    )
    project_name: str | None = Field(
        default=None,
        description="Project name.",
    )
    project_goal: str | None = Field(
        default=None,
        description="Project goal.",
    )
    project_background: str | None = Field(
        default=None,
        description="Project background.",
    )
    domain: str | None = Field(
        default=None,
        description="Project domain.",
    )
    current_stage: str | None = Field(
        default=None,
        description="Current project stage.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description=(
            "Structured project-level constraints with durable value across sessions."
        ),
    )
    important_context: str | None = Field(
        default=None,
        description="Important context that remains useful for understanding the project.",
    )
    record_status: str = Field(
        min_length=1,
        description=(
            "Lifecycle status of this memory record, such as active, superseded, "
            "archived, or pruned."
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="Confidence score for the current project profile record.",
    )
    supersedes_profile_id: str | None = Field(
        default=None,
        description="Optional older project profile record replaced by this profile.",
    )
    superseded_by_profile_id: str | None = Field(
        default=None,
        description="Optional newer project profile record that replaced this profile.",
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
        description="Timestamp when this project profile record was created.",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp when this project profile record was last updated.",
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
        description="Optional supporting source references for this project profile record.",
    )
