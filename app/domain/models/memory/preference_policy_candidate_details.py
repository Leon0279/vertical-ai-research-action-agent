"""Typed details proposed for preference or research policy memory."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class PreferencePolicyCandidateDetails(BaseModel):
    """LLM-supported business fields for a preference/policy candidate."""

    model_config = ConfigDict(extra="forbid")

    target_scope_type: Literal["task_type", "memory_type"] | None = None
    target_scope_value: str | None = None
    policy_type: str | None = None
    policy_text: str | None = None
    conditions: dict[str, JsonValue] = Field(default_factory=dict)
    priority: int | None = None
    enforcement_level: Literal["soft", "default", "strict"] | None = None

    @model_validator(mode="after")
    def validate_target_scope_pair(self) -> "PreferencePolicyCandidateDetails":
        """Require target scope type and value to be supplied together."""

        if (self.target_scope_type is None) != (self.target_scope_value is None):
            raise ValueError(
                "target_scope_type and target_scope_value must both be set or both be null"
            )
        return self
