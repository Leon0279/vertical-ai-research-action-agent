"""Domain model for Evidence Processing results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.models.evidence.processed_evidence_unit import ProcessedEvidenceUnit

EvidenceProcessingStatus = Literal["success", "partial_success", "no_result", "failed"]


class EvidenceProcessingResult(BaseModel):
    """Result of converting candidate materials into processed evidence units."""

    processed_evidence_units: list[ProcessedEvidenceUnit] = Field(
        default_factory=list,
        description="Current-round processed evidence units.",
    )
    evidence_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Lightweight summary of the processed evidence result.",
    )
    evidence_processing_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Processing counts and observability metadata.",
    )
    processing_status: EvidenceProcessingStatus = Field(
        description="Overall evidence processing status.",
    )
    error_info: str | None = Field(
        default=None,
        description="Failure or partial-failure explanation, if any.",
    )
