"""Domain model for family selection results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SelectionStatus = Literal["selected", "no_match", "failed"]


class FamilySelectionResult(BaseModel):
    """Output of family-level routing before any tool-level selection occurs."""

    candidate_families: list[str] = Field(
        default_factory=list,
        description="Families that remain after scope and constraint filtering.",
    )
    ranked_candidate_families: list[str] = Field(
        default_factory=list,
        description="Candidate families ordered by the deterministic selection policy.",
    )
    selected_family: str | None = Field(
        default=None,
        description="Selected family for downstream family service invocation.",
    )
    selection_status: SelectionStatus = Field(
        description="Whether a family was selected, no family matched, or selection failed.",
    )
    selection_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Compact summary of selection inputs and outcome.",
    )
    selection_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="Detailed trace of family scoping, filtering, and ranking.",
    )
    error_info: str | None = Field(
        default=None,
        description="Top-level selection failure or no-match explanation.",
    )
