"""Domain model for llms_txt_docs_search tool results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AcquisitionStatus = Literal["success", "partial_success", "no_result", "failed"]


class LlmsTxtDocsSearchToolResult(BaseModel):
    """Normalized runtime output returned by the llms_txt_docs_search tool."""

    normalized_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Unified candidate material items for downstream evidence processing.",
    )
    acquisition_status: AcquisitionStatus = Field(
        description="Overall acquisition status for the tool execution.",
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description="Number of items dropped during adapter or tool-level normalization.",
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of selected family/tool and normalized item counts.",
    )
    execution_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution-level counts and degradation signals for observability.",
    )
    retrieval_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="Compact trace of selected sources and returned references.",
    )
    error_info: str | None = Field(
        default=None,
        description="Top-level failure explanation when acquisition_status is failed.",
    )
