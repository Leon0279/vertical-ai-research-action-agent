"""Typed result models for memory persistence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import MemoryType

PersistenceAction = Literal[
    "create",
    "update",
    "replace",
    "append_supersede",
    "status_transition",
    "no_write",
    "failed",
]

PersistenceItemStatus = Literal["written", "no_write", "failed"]


class MemoryPersistenceItemResult(BaseModel):
    """单个 memory candidate 的持久化处理结果。"""

    memory_type: MemoryType
    action: PersistenceAction
    status: PersistenceItemStatus
    project_scope_id: str | None = None
    written_record_id: str | None = None
    affected_existing_record_ids: list[str] = Field(default_factory=list)
    supersession_applied: bool = False
    status_transition_applied: bool = False
    no_write_reason: str | None = None
    error_info: str | None = None


class MemoryPersistenceResult(BaseModel):
    """一次批量 memory write-back 的汇总结果。"""

    items: list[MemoryPersistenceItemResult] = Field(default_factory=list)
    written_count: int = 0
    no_write_count: int = 0
    failed_count: int = 0
