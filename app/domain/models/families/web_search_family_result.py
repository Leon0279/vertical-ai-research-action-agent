"""Domain model for web_search family results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AcquisitionStatus = Literal["success", "partial_success", "no_result", "failed"]


class WebSearchFamilyResult(BaseModel):
    """Normalized family-level output returned by the web_search family service."""

    normalized_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Unified candidate material items for downstream evidence processing.",
    )
    acquisition_status: AcquisitionStatus = Field(
        description="Overall acquisition status for the family execution.",
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description="Number of items dropped during tool or family-level normalization.",
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of selected family/tool and normalized item counts.",
    )
    execution_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution-level counts and family-level selection signals.",
    )
    retrieval_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="Compact trace of family selection and underlying tool execution.",
    )
    error_info: str | None = Field(
        default=None,
        description="Top-level failure explanation when acquisition_status is failed.",
    )
    selected_family: str = Field(
        default="web_search",
        description="Family selected by the upstream execution layer.",
    )
    candidate_tools: list[str] = Field(
        default_factory=list,
        description="Candidate tools considered inside the selected family.",
    )
    selected_tool: str | None = Field(
        default=None,
        description="Concrete tool selected inside the family for execution.",
    )
