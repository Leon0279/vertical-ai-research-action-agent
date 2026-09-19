"""Public Policy Memory item response schema."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class PolicyMemoryItemResponse(BaseModel):
    """公开一条 Policy Memory 的业务字段，不暴露内部 owner 标识或治理信息。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    policy_id: str = Field(min_length=1)
    owner_scope_type: Literal["project", "user", "global"]
    target_scope_type: Literal["task_type", "memory_type"] | None = None
    target_scope_value: str | None = None
    policy_type: str = Field(min_length=1)
    policy_text: str = Field(min_length=1)
    conditions: dict[str, JsonValue] = Field(default_factory=dict)
    priority: int | None = None
    enforcement_level: str | None = None
    confidence: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    derived_from_session_id: str | None = None
    derived_from_run_id: str | None = None
    source_refs: list[str] = Field(default_factory=list)
