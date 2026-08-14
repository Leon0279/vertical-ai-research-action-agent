"""Domain model for compact session continuity memory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.memory.session_turn_summary import SessionTurnSummary


class SessionMemory(BaseModel):
    """表示单个用户会话的紧凑工作记忆。

Redis-backed compact working memory for one user session."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(
        min_length=1,
        description="用户归属边界，用于保证不同用户的 session memory 隔离。",
    )
    session_id: str = Field(
        min_length=1,
        description=(
            "连续多轮对话 session 的边界。Session Memory 的 Redis key 应继续使用 "
            "user_id + session_id，例如 session_memory:{user_id}:{session_id}。"
        ),
    )
    session_working_summary: str | None = Field(
        default=None,
        description=(
            "当前 session 的主线工作摘要，是 session continuity 的核心载体。"
            "它强调当前还在工作的连续性状态，而不是普通会话摘要。"
        ),
    )
    recent_turn_summaries: list[SessionTurnSummary] = Field(
        default_factory=list,
        description=(
            "最近若干轮对话的压缩摘要窗口，不是原始 turn 内容。"
            "该字段应 bounded append，不应无限增长。"
        ),
    )
    latest_recommendation: str | None = Field(
        default=None,
        description=(
            "当前 session 中最近形成、仍然有效的 recommendation / conclusion。"
            "它应采用 overwrite，不应长期并列保留多个 latest recommendation。"
        ),
    )
    latest_action_items: list[str] = Field(
        default_factory=list,
        description=(
            "当前仍有效的 next steps / action items。"
            "它应采用 structured refresh / overwrite，已完成、取消或被替代的 action items 应移除。"
        ),
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="当前 session 中仍未解决的问题集合。该字段应支持 merge / remove，而不是纯 append。",
    )
    current_local_task_framing: str | None = Field(
        default=None,
        description=(
            "当前局部任务 framing，例如当前是在解释概念、比较方案、写 LLD、"
            "收敛决策，还是规划 action。它表达的是当前任务形态，不只是一个话题标题。"
        ),
    )
    temporary_context: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "极短期、低结构化的 session-local scratchpad。只放当前 run 可能需要但不值得"
            "提升为正式字段的临时信息，例如 active_section、临时约束、局部备注。"
            "该字段要谨慎使用，不能变成杂物桶。"
        ),
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Session Memory 最近更新时间。",
    )
    expires_at: datetime | None = Field(
        default=None,
        description=(
            "逻辑过期时间，应与 Redis TTL 对齐。Redis TTL 只清理 compact working memory，"
            "不影响 long-term memory；若未来启用 Message Log，完整消息历史仍可保留。"
        ),
    )
