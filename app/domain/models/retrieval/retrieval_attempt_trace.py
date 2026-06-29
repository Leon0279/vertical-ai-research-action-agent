"""Typed trace for one retrieval attempt."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RetrievalAttemptTrace(BaseModel):
    """Compact trace for a single TEL family execution attempt."""

    selected_family: str | None = None
    generated_query: str | None = None
    query_focus: str | None = None
    acquisition_status: str | None = None
    evaluation_status: str | None = None
    recovery_action: str | None = None
    next_step_hint: str | None = None
    retry_count: int = Field(default=0, ge=0)
    fallback_applied: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_mapping(cls, value: Any) -> Any:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        known = {
            "selected_family",
            "generated_query",
            "query_focus",
            "acquisition_status",
            "evaluation_status",
            "recovery_action",
            "next_step_hint",
            "retry_count",
            "fallback_applied",
            "metadata",
        }
        metadata = dict(value.get("metadata") or {}) if isinstance(value.get("metadata"), Mapping) else {}
        for key, item in value.items():
            if key not in known:
                metadata[key] = item
        normalized = {
            key: value.get(key)
            for key in known
            if key != "metadata" and key in value
        }
        normalized["metadata"] = metadata
        return normalized

    def to_legacy_dict(self) -> dict[str, Any]:
        data = self.model_dump(exclude={"metadata"})
        data.update(self.metadata)
        return data
