"""Typed processing summary for EvidenceProcessingService."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceProcessingSummary(BaseModel):
    """Processing counts and observability for evidence processing."""

    policy: str | None = None
    input_material_count: int = Field(default=0, ge=0)
    deduped_material_count: int = Field(default=0, ge=0)
    removed_duplicate_count: int = Field(default=0, ge=0)
    exact_duplicate_removed: int = Field(default=0, ge=0)
    high_overlap_removed: int = Field(default=0, ge=0)
    dropped_material_count: int = Field(default=0, ge=0)
    structured_evidence_count: int = Field(default=0, ge=0)
    merged_evidence_count: int = Field(default=0, ge=0)
    output_evidence_count: int = Field(default=0, ge=0)
    llm_invalid_output_count: int = Field(default=0, ge=0)
    upstream_acquisition_status: str | None = None
    upstream_dropped_item_count: int = Field(default=0, ge=0)
    short_circuit_reason: str | None = None
    observability: dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.observability.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.observability and not hasattr(self, key):
            raise KeyError(key)
        return value
