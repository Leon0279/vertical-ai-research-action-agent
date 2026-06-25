"""Domain model for retrieval query generation results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

GenerationStatus = Literal["succeeded", "failed"]


class RetrievalQueryGenerationResult(BaseModel):
    """Output of generating an initial retrieval query for a selected family."""

    selected_family: str | None = Field(
        default=None,
        description="Selected family this query was generated for; never a selected tool.",
    )
    generated_query: str | None = Field(
        default=None,
        description="Initial retrieval query generated for downstream family execution.",
    )
    query_focus: str | None = Field(
        default=None,
        description="Short label describing the generated query's retrieval focus.",
    )
    preserved_terms: list[str] = Field(
        default_factory=list,
        description="High-information terms preserved in the generated query.",
    )
    generation_status: GenerationStatus = Field(
        description="Whether query generation succeeded or failed.",
    )
    generation_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Compact summary of query generation policy and outcome.",
    )
    generation_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="Trace of normalized inputs and parser details for observability.",
    )
    error_info: str | None = Field(
        default=None,
        description="Top-level failure explanation when generation_status is failed.",
    )
