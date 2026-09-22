"""Domain model for one conversation_sessions row."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.domain.enums import ConversationSessionStatus


class ConversationSessionRecord(BaseModel):
    """表示一个可持久回看的 conversation session 及其轻量元数据。"""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1,
        description="必填字段。跨多轮消息保持稳定的会话标识。",
    )
    user_id: str = Field(
        min_length=1,
        description="必填字段。会话所属用户标识，是读取和写入时的隔离边界。",
    )
    project_id: str | None = Field(
        default=None,
        description="可选字段。会话所属项目的稳定标识；无项目范围的会话为 None。",
    )
    title: str | None = Field(
        default=None,
        description="可选字段。用于历史列表展示的会话标题；尚未生成时为 None。",
    )
    session_status: ConversationSessionStatus = Field(
        default=ConversationSessionStatus.ACTIVE,
        description="可选字段。会话生命周期状态，默认 active。",
    )
    created_at: datetime | None = Field(
        default=None,
        description="可选字段。会话首次持久化时间；缺失时由 Store 写入当前 UTC 时间。",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="可选字段。会话元数据或消息活跃时间最近发生变化的时间。",
    )
    last_message_at: datetime | None = Field(
        default=None,
        description="可选字段。该会话最近一条已记录消息的创建时间。",
    )
    archived_at: datetime | None = Field(
        default=None,
        description="可选字段。会话被归档的时间；未归档时为 None。",
    )
    deleted_at: datetime | None = Field(
        default=None,
        description="可选字段。会话被软删除的时间；未删除时为 None。",
    )
    metadata_json: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="可选字段。会话级 JSON-safe 扩展信息，不保存完整消息正文或执行 trace。",
    )
