"""Compressed representation of one recent session turn."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionTurnSummary(BaseModel):
    """汇总会话轮次的关键信息。

Lightweight turn summary for session continuity."""

    model_config = ConfigDict(extra="forbid")

    role: str = Field(
        min_length=1,
        description="被压缩摘要的 turn 角色，例如 user 或 assistant。",
    )
    content_summary: str = Field(
        min_length=1,
        description="该 turn 的轻量内容摘要，不保存原始完整消息。",
    )
    created_at: datetime | None = Field(
        default=None,
        description="该 turn 摘要对应的创建时间。",
    )
