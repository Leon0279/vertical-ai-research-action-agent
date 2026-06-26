"""Domain model for Tool Execution Layer requests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models.tool_execution_layer.evidence_shape import EvidenceShape
from app.domain.models.tool_execution_layer.family_selection_request import ActionMode
from app.domain.models.tool_execution_layer.request_completion_evaluation_request import (
    FallbackPolicy,
)
from app.domain.models.tool_execution_layer.retrieval_query_generation_request import (
    RetrievalFamily,
)


class ToolExecutionLayerRequest(BaseModel):
    """Research Executor-facing input for one Tool Execution Layer request."""

    target_problem: str = Field(description="Current retrieval target problem.")
    action_mode: ActionMode = Field(
        default="external_acquisition",
        description="High-level acquisition mode used to scope candidate families.",
    )
    evidence_goal: str | None = Field(
        default=None,
        description="Optional evidence acquisition goal.",
    )
    evidence_shape: EvidenceShape | None = Field(
        default=None,
        description="Optional desired evidence shape.",
    )
    task_framing: str | None = Field(
        default=None,
        description="Optional task framing signal.",
    )
    allowed_source_families: list[RetrievalFamily] = Field(
        default_factory=list,
        description="Families allowed for this request.",
    )
    preferred_source_families: list[RetrievalFamily] = Field(
        default_factory=list,
        description="Preference-ordered families supplied by the Research Executor.",
    )
    blocked_source_families: list[RetrievalFamily] = Field(
        default_factory=list,
        description="Families that must not be selected.",
    )
    available_families: list[RetrievalFamily] = Field(
        default_factory=list,
        description="Families available to the current runtime request.",
    )
    success_hint: str | None = Field(
        default=None,
        description="Hint describing what useful retrieval results should look like.",
    )
    recent_low_value_queries: list[str] = Field(
        default_factory=list,
        description="Recent low-value query phrasings to avoid.",
    )
    preferred_tool: str | None = Field(
        default=None,
        description="Optional Research Executor-owned preferred tool hint.",
    )
    source_names: list[str] = Field(
        default_factory=list,
        description="Optional docs source names.",
    )
    include_domains: list[str] = Field(
        default_factory=list,
        description="Optional web domains to include.",
    )
    exclude_domains: list[str] = Field(
        default_factory=list,
        description="Optional web domains to exclude.",
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description="Maximum family search results to request.",
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description="Maximum content fetches for web or paper families.",
    )
    min_score_threshold: float = Field(
        default=0.5,
        ge=0.0,
        description="Minimum score threshold for web content fetch candidate selection.",
    )
    owner_user_id: str | None = Field(
        default=None,
        description="Required owner boundary when research_knowledge_recall is selected.",
    )
    query_embedding: list[float] | None = Field(
        default=None,
        min_length=1,
        description="Optional precomputed embedding for memory recall.",
    )
    project_scope_id: str | None = Field(
        default=None,
        description="Optional project scope for memory recall.",
    )
    allowed_visibility_scopes: list[str] = Field(
        default_factory=lambda: ["user"],
        description="Visibility scopes allowed for memory recall.",
    )
    knowledge_types: list[str] = Field(
        default_factory=list,
        description="Optional memory knowledge type filters.",
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description="Optional memory topic tag filters.",
    )
    source_types: list[str] = Field(
        default_factory=list,
        description="Optional memory source type filters.",
    )
    memory_recall_limit: int = Field(
        default=5,
        ge=1,
        description="Maximum recalled memory units.",
    )
    retry_budget: int = Field(
        default=1,
        ge=0,
        description="Maximum internal retry attempts for this Tool Execution Layer request.",
    )
    fallback_policy: FallbackPolicy = Field(
        default="fallback_within_same_family",
        description="Fallback policy for this request.",
    )
    timeout_limit_ms: int | None = Field(
        default=None,
        gt=0,
        description="Optional total Tool Execution Layer request timeout budget.",
    )


ExecutionStatus = Literal["completed", "failed"]
