"""Public response schema for a project Memory summary."""

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.memory_collection_summary_response import (
    MemoryCollectionSummaryResponse,
)


class MemorySummaryResponse(BaseModel):
    """公开当前项目上下文中各类长期 Memory 的概览。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    project_id: str = Field(min_length=1)
    project_profile: MemoryCollectionSummaryResponse
    decisions: MemoryCollectionSummaryResponse
    actions: MemoryCollectionSummaryResponse
    policies: MemoryCollectionSummaryResponse
    research_knowledge: MemoryCollectionSummaryResponse
