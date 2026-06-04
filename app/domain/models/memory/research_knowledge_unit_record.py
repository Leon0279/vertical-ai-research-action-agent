"""Domain model for one research_knowledge_units row."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResearchKnowledgeUnitRecord(BaseModel):
    """Typed research knowledge unit aligned with the LLD storage schema."""

    model_config = ConfigDict(extra="forbid")

    knowledge_id: str = Field(
        min_length=1,
        description="Primary identifier for one reusable research knowledge unit.",
    )
    owner_user_id: str = Field(
        min_length=1,
        description="User ownership boundary used to isolate research knowledge records.",
    )
    project_scope_id: str | None = Field(
        default=None,
        description="Optional project-level scope for project-specific knowledge recall.",
    )
    visibility_scope: str = Field(
        min_length=1,
        description="Declared visibility scope, such as user, project, domain, or global.",
    )
    visibility_scope_effective: str = Field(
        min_length=1,
        description="Effective visibility scope used by the read path filter.",
    )
    title: str = Field(
        min_length=1,
        description="Short title for the knowledge unit.",
    )
    summary: str = Field(
        min_length=1,
        description="Summary-level reusable research knowledge, not raw source text.",
    )
    knowledge_type: str = Field(
        min_length=1,
        description=(
            "Knowledge category, such as concept, method, comparison, conclusion, "
            "tradeoff, or pattern."
        ),
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description="Topic tags used for metadata filtering before semantic recall.",
    )
    confidence: float | None = Field(
        default=None,
        description="Confidence score for this knowledge unit.",
    )
    source_refs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Evidence-level source references supporting this knowledge unit.",
    )
    source_type: str | None = Field(
        default=None,
        description="Primary source type, such as paper, web_page, user_upload, conversation, or run_output.",
    )
    derived_from_session_id: str | None = Field(
        default=None,
        description="Optional source session identifier from which this unit was distilled.",
    )
    derived_from_run_id: str | None = Field(
        default=None,
        description="Optional source run identifier from which this unit was distilled.",
    )
    created_by: str | None = Field(
        default=None,
        description="Optional creator label, such as system, user, or llm.",
    )
    status: str = Field(
        min_length=1,
        description="Knowledge lifecycle status, such as active, superseded, archived, or pruned.",
    )
    created_at: datetime | None = Field(
        default=None,
        description="Timestamp when this knowledge unit was created.",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp when this knowledge unit was last updated.",
    )
    archived_at: datetime | None = Field(
        default=None,
        description="Timestamp when this knowledge unit was archived.",
    )
    pruned_at: datetime | None = Field(
        default=None,
        description="Timestamp when this knowledge unit was pruned.",
    )
    freshness_sensitivity: str | None = Field(
        default=None,
        description="How likely this knowledge is to become stale, such as low, medium, or high.",
    )
    freshness_status: str | None = Field(
        default=None,
        description="Current freshness state, such as fresh, aging, or stale.",
    )
    last_verified_at: datetime | None = Field(
        default=None,
        description="Timestamp when this knowledge was last verified against evidence.",
    )
    freshness_checked_at: datetime | None = Field(
        default=None,
        description="Timestamp when this knowledge last received freshness evaluation.",
    )
    staleness_reason: str | None = Field(
        default=None,
        description="Optional reason explaining why freshness was downgraded.",
    )
    dedupe_key: str | None = Field(
        default=None,
        description="Normalized key used to identify near-duplicate knowledge units.",
    )
    canonical_knowledge_id: str | None = Field(
        default=None,
        description="Canonical knowledge identifier this record belongs to.",
    )
    is_canonical: bool = Field(
        default=True,
        description="Whether this record is the canonical knowledge unit for recall.",
    )
    merged_into_id: str | None = Field(
        default=None,
        description="Target knowledge id when this unit has been merged into another unit.",
    )
    embedding_text: str | None = Field(
        default=None,
        description="Text used to generate the embedding, usually title plus summary.",
    )
    embedding_vector: list[float] | None = Field(
        default=None,
        description="Embedding vector used by pgvector semantic recall.",
    )
    embedding_model: str | None = Field(
        default=None,
        description="Embedding model used to generate the vector representation.",
    )
    embedding_version: str | None = Field(
        default=None,
        description="Version of the embedding model or embedding generation configuration.",
    )
