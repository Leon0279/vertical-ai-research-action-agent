"""Public summary of one persistent conversation session."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ConversationSessionStatus


class ConversationSessionSummary(BaseModel):
    """表示历史会话列表中一条轻量 session 信息。"""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1,
        description="必填字段。可用于继续对话或查询消息历史的稳定会话标识。",
    )
    project_id: str | None = Field(
        default=None,
        description="可选字段。会话所属项目标识；无项目范围时为 None。",
    )
    title: str | None = Field(
        default=None,
        description="可选字段。用于历史列表展示的会话标题。",
    )
    session_status: ConversationSessionStatus = Field(
        description="必填字段。会话当前的 active 或 archived 生命周期状态。",
    )
    created_at: datetime = Field(
        description="必填字段。会话首次持久化的时间。",
    )
    updated_at: datetime = Field(
        description="必填字段。会话元数据或消息活跃时间最近发生变化的时间。",
    )
    last_message_at: datetime | None = Field(
        default=None,
        description="可选字段。会话最近一条已记录消息的创建时间。",
    )
