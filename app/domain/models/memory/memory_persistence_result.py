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

    memory_type: MemoryType = Field(description="必填字段。当前处理的 MemoryCandidate 所属 memory 类型，用于说明写入目标和生命周期语义。")
    action: PersistenceAction = Field(description="必填字段。持久化层为该 candidate 决定的操作，例如 create、replace、no_write 或 failed。")
    status: PersistenceItemStatus = Field(description="必填字段。该 candidate 的最终处理状态：已写入、未写入或处理失败。")
    project_scope_id: str | None = Field(
        default=None,
        description="可选字段。该持久化项所属项目范围；无项目边界的 user-level memory 为 None。",
    )
    written_record_id: str | None = Field(
        default=None,
        description="可选字段。成功写入或更新后对应 durable record 的标识；no_write 或失败时为 None。",
    )
    affected_existing_record_ids: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。本次操作比较、替换、supersede 或状态迁移影响到的已有 record 标识。",
    )
    supersession_applied: bool = Field(
        default=False,
        description="可选字段，默认 False。是否已通过本次操作让旧记录被新版本 supersede。",
    )
    status_transition_applied: bool = Field(
        default=False,
        description="可选字段，默认 False。是否已对已有 action record 执行状态迁移。",
    )
    no_write_reason: str | None = Field(
        default=None,
        description="可选字段。未写入时的确定性原因，例如 duplicate、unsupported_type 或 admission_failed。",
    )
    error_info: str | None = Field(
        default=None,
        description="可选字段。单条 candidate 持久化异常的摘要；用于观测，不应写入 durable memory。",
    )


class MemoryPersistenceResult(BaseModel):
    """一次批量 memory write-back 的汇总结果。"""

    items: list[MemoryPersistenceItemResult] = Field(
        default_factory=list,
        description="可选字段，默认空列表。本次批量 write-back 中每个 candidate 的处理结果，顺序与处理顺序一致。",
    )
    written_count: int = Field(default=0, description="本批次成功写入、更新或完成生命周期操作的 candidate 数量。")
    no_write_count: int = Field(default=0, description="本批次因重复、准入规则或不支持类型而未写入的 candidate 数量。")
    failed_count: int = Field(default=0, description="本批次在 lookup、语义解析或 store 写入阶段发生异常的 candidate 数量。")
