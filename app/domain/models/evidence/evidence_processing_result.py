"""Domain model for Evidence Processing results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models.evidence.evidence_processing_summary import EvidenceProcessingSummary
from app.domain.models.evidence.processed_evidence_summary import ProcessedEvidenceSummary
from app.domain.models.evidence.processed_evidence_unit import ProcessedEvidenceUnit

EvidenceProcessingStatus = Literal["success", "partial_success", "no_result", "failed"]


class EvidenceProcessingResult(BaseModel):
    """Result of converting candidate materials into processed evidence units."""

    processed_evidence_units: list[ProcessedEvidenceUnit] = Field(
        default_factory=list,
        description="Current-round processed evidence units.",
    )
    evidence_summary: ProcessedEvidenceSummary = Field(
        default_factory=ProcessedEvidenceSummary,
        description="Lightweight summary of the processed evidence result.",
    )
    evidence_processing_summary: EvidenceProcessingSummary = Field(
        default_factory=EvidenceProcessingSummary,
        description="Processing counts and observability metadata.",
    )
    processing_status: EvidenceProcessingStatus = Field(
        description="Overall evidence processing status.",
    )
    error_info: str | None = Field(
        default=None,
        description="Failure or partial-failure explanation, if any.",
    )
