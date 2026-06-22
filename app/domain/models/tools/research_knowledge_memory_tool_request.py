"""Domain model for research_knowledge_memory tool requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchKnowledgeMemoryToolRequest(BaseModel):
    """Runtime-facing input for the research_knowledge_memory tool."""

    owner_user_id: str = Field(
        min_length=1,
        description="User ownership boundary for research knowledge recall.",
    )
    query_text: str | None = Field(
        default=None,
        description="Optional textual recall query used when no precomputed embedding is supplied.",
    )
    query_embedding: list[float] | None = Field(
        default=None,
        min_length=1,
        description="Optional precomputed embedding to reuse for semantic recall.",
    )
    project_scope_id: str | None = Field(
        default=None,
        description="Optional project scope for project-aware knowledge recall.",
    )
    allowed_visibility_scopes: list[str] = Field(
        default_factory=lambda: ["user"],
        description="Visibility scopes allowed for this recall path.",
    )
    knowledge_types: list[str] = Field(
        default_factory=list,
        description="Optional knowledge type filters.",
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description="Optional topic tag filters.",
    )
    source_types: list[str] = Field(
        default_factory=list,
        description="Optional source type filters.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        description="Maximum number of recalled knowledge units to request.",
    )
