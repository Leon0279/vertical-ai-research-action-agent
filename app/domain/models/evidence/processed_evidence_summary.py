"""Typed summary for processed evidence output."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProcessedEvidenceSummary(BaseModel):
    """Lightweight summary of evidence units produced in one processing round."""

    new_evidence_count: int = Field(default=0, ge=0)
    evidence_type_breakdown: dict[str, int] = Field(default_factory=dict)
    source_coverage_summary: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.metadata and not hasattr(self, key):
            raise KeyError(key)
        return value
