"""Domain model for long-term memory records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums.memory_type import MemoryType


class MemoryRecord(BaseModel):
    """Durable long-term memory record."""

    record_id: str = Field(description="必填字段。通用长期 memory record 的稳定标识，用于存储、更新和关联。")
    memory_type: MemoryType = Field(description="必填字段。该记录承载的 memory 语义类型，决定其 payload 解释和生命周期策略。")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="可选字段，默认空字典。通用 record 的 JSON-safe 内容；typed memory record 应优先使用正式字段而非依赖此字段承载核心语义。",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="记录首次创建时间，默认使用 UTC 当前时间。",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="记录最近一次更新的时间，默认使用 UTC 当前时间。",
    )
