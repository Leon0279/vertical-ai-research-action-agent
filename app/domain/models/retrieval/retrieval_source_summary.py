"""Typed source summary for retrieval outputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RetrievalSourceSummary(BaseModel):
    """Source provenance summary shared across tool, family, and TEL results."""

    selected_family: str | None = Field(default=None, description="Selected retrieval family.")
    selected_tool: str | None = Field(default=None, description="Tool selected inside the family, when known.")
    normalized_count: int = Field(default=0, ge=0, description="Count of normalized candidate materials.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional source/provenance details outside the stable shared contract.",
    )

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_mapping(cls, value: Any) -> Any:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        metadata = dict(value.get("metadata") or {}) if isinstance(value.get("metadata"), Mapping) else {}
        known = {"selected_family", "selected_tool", "normalized_count", "metadata"}
        for key, item in value.items():
            if key not in known:
                metadata[key] = item
        return {
            "selected_family": value.get("selected_family"),
            "selected_tool": value.get("selected_tool"),
            "normalized_count": value.get("normalized_count") or 0,
            "metadata": metadata,
        }

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.metadata and not hasattr(self, key):
            raise KeyError(key)
        return value

    def __iter__(self):
        yield from self.to_legacy_dict().items()

    def to_legacy_dict(self) -> dict[str, Any]:
        data = {
            "selected_family": self.selected_family,
            "selected_tool": self.selected_tool,
            "normalized_count": self.normalized_count,
        }
        data.update(self.metadata)
        return data
