"""Typed execution summary for retrieval outputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RetrievalExecutionSummary(BaseModel):
    """Execution counts and recovery signals shared across retrieval layers."""

    policy: str | None = Field(default=None, description="Execution policy name.")
    execution_status: str | None = Field(default=None, description="Layer execution status, when applicable.")
    normalized_count: int | None = Field(default=None, ge=0, description="Normalized item count, when reported.")
    dropped_item_count: int | None = Field(default=None, ge=0, description="Dropped item count, when reported.")
    retry_count: int = Field(default=0, ge=0, description="Retry attempts consumed by TEL.")
    fallback_applied: bool = Field(default=False, description="Whether broader fallback was applied.")
    recovery_attempt_count: int = Field(default=0, ge=0, description="Recovery attempts consumed by TEL.")
    recovery_exhausted_reason: str | None = Field(default=None, description="Reason recovery stopped, if any.")
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool/family-specific numeric counters and lightweight metrics.",
    )
    observability: dict[str, Any] = Field(
        default_factory=dict,
        description="Status/debug fields that are useful for tracing but not stable API fields.",
    )

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_mapping(cls, value: Any) -> Any:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        known = {
            "policy",
            "execution_status",
            "normalized_count",
            "dropped_item_count",
            "retry_count",
            "fallback_applied",
            "recovery_attempt_count",
            "recovery_exhausted_reason",
            "metrics",
            "observability",
        }
        metrics = dict(value.get("metrics") or {}) if isinstance(value.get("metrics"), Mapping) else {}
        observability = (
            dict(value.get("observability") or {})
            if isinstance(value.get("observability"), Mapping)
            else {}
        )
        for key, item in value.items():
            if key in known:
                continue
            if key.endswith("_count") or key.endswith("_ms") or isinstance(item, (int, float)):
                metrics[key] = item
            else:
                observability[key] = item
        return {
            "policy": value.get("policy"),
            "execution_status": value.get("execution_status"),
            "normalized_count": value.get("normalized_count"),
            "dropped_item_count": value.get("dropped_item_count"),
            "retry_count": value.get("retry_count") or 0,
            "fallback_applied": bool(value.get("fallback_applied")),
            "recovery_attempt_count": value.get("recovery_attempt_count") or 0,
            "recovery_exhausted_reason": value.get("recovery_exhausted_reason"),
            "metrics": metrics,
            "observability": observability,
        }

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.metrics:
            return self.metrics[key]
        return self.observability.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.metrics and key not in self.observability and not hasattr(self, key):
            raise KeyError(key)
        return value

    def __iter__(self):
        yield from self.to_legacy_dict().items()

    def to_legacy_dict(self) -> dict[str, Any]:
        data = {
            "policy": self.policy,
            "execution_status": self.execution_status,
            "normalized_count": self.normalized_count,
            "dropped_item_count": self.dropped_item_count,
            "retry_count": self.retry_count,
            "fallback_applied": self.fallback_applied,
            "recovery_attempt_count": self.recovery_attempt_count,
            "recovery_exhausted_reason": self.recovery_exhausted_reason,
        }
        data.update(self.metrics)
        data.update(self.observability)
        return data
