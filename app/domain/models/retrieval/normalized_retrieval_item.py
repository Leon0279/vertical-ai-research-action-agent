"""Typed candidate material item returned by retrieval tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.source import SourceReference


class NormalizedRetrievalItem(BaseModel):
    """Unified candidate material item consumed by evidence processing."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(default="", description="Stable item identifier within a retrieval result.")
    source_family: str = Field(default="", description="Retrieval family that produced this item.")
    source_reference: SourceReference = Field(
        description="Canonical source reference for provenance and downstream evidence processing."
    )
    content: str = Field(default="", description="Candidate material content for evidence processing.")
    content_type: str | None = Field(default=None, description="Content shape, such as text_snippet or document_chunk.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool/provider-specific metadata that should not be part of the shared item contract.",
    )

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.metadata and not hasattr(self, key):
            raise KeyError(key)
        return value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return all(self.get(key) == value for key, value in other.items())
        return super().__eq__(other)
