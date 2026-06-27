"""Domain model for Evidence Processing requests."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.families.base_family_execution_result import AcquisitionStatus


class EvidenceProcessingRequest(BaseModel):
    """Input for converting Tool Execution Layer outputs into evidence units."""

    normalized_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Final candidate materials from the Tool Execution Layer.",
    )
    acquisition_status: AcquisitionStatus = Field(
        description="Final Tool Execution Layer acquisition status.",
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description="Item count dropped before evidence processing.",
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool Execution Layer source summary.",
    )
    execution_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool Execution Layer execution summary.",
    )
    retrieval_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool Execution Layer retrieval trace.",
    )
