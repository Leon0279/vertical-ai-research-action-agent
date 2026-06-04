"""Query object for research knowledge semantic recall."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResearchKnowledgeRecallQuery(BaseModel):
    """Metadata filters plus a precomputed query embedding for knowledge recall."""

    model_config = ConfigDict(extra="forbid")

    owner_user_id: str = Field(
        min_length=1,
        description="Current user ownership boundary for the recall query.",
    )
    query_embedding: list[float] = Field(
        min_length=1,
        description="Already generated embedding vector for the recall query.",
    )
    allowed_visibility_scopes: list[str] = Field(
        default_factory=lambda: ["user"],
        description="Visibility scopes allowed for this read path.",
    )
    project_scope_id: str | None = Field(
        default=None,
        description="Optional project scope for project-aware knowledge recall.",
    )
    knowledge_types: list[str] = Field(
        default_factory=list,
        description="Optional knowledge type filter.",
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description="Optional topic tag overlap filter.",
    )
    source_types: list[str] = Field(
        default_factory=list,
        description="Optional source type filter.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        description="Requested bounded recall size before adapter-level max limit capping.",
    )
