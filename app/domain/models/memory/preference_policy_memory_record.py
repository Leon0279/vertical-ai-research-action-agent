"""Domain model for one preference_policy_memory row."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PreferencePolicyMemoryRecord(BaseModel):
    """Typed preference/policy memory record aligned with the adjusted table schema."""

    model_config = ConfigDict(extra="forbid")

    policy_id: str = Field(
        min_length=1,
        description="Primary identifier for one durable preference or policy record.",
    )
    user_id: str = Field(
        min_length=1,
        description="Owner user identifier for this policy record.",
    )
    project_id: str | None = Field(
        default=None,
        description="Optional project identifier when the rule is project-scoped.",
    )
    owner_scope_type: str = Field(
        min_length=1,
        description="Owner scope layer of the rule, such as global, user, or project.",
    )
    owner_scope_value: str | None = Field(
        default=None,
        description="Optional owner scope discriminator, such as the system owner id for global rules.",
    )
    target_scope_type: str | None = Field(
        default=None,
        description="Optional target scope type, such as task_type or memory_type.",
    )
    target_scope_value: str | None = Field(
        default=None,
        description="Optional target scope value that refines where the rule applies.",
    )
    policy_type: str = Field(
        min_length=1,
        description="Rule category, such as preference, constraint, format_rule, or behavior_rule.",
    )
    policy_text: str = Field(
        min_length=1,
        description="Reusable rule text or policy statement.",
    )
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional JSON conditions that further constrain when the rule should apply.",
    )
    priority: int | None = Field(
        default=None,
        description="Conflict-handling priority for this rule.",
    )
    enforcement_level: str | None = Field(
        default=None,
        description="Execution strength of the rule, such as soft, default, or strict.",
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
        description="Confidence score for the current preference/policy record.",
    )
    supersedes_policy_id: str | None = Field(
        default=None,
        description="Optional older policy record superseded by this rule.",
    )
    superseded_by_policy_id: str | None = Field(
        default=None,
        description="Optional newer policy record that superseded this rule.",
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
        description="Timestamp when this preference/policy record was created.",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Timestamp when this preference/policy record was last updated.",
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
        description="Optional supporting source references for this policy record.",
    )
