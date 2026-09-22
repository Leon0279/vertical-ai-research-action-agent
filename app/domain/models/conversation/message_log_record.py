"""Domain model for one message_log row."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.domain.enums import ConversationContentFormat, ConversationMessageRole


class MessageLogRecord(BaseModel):
    """表示一条用于历史回看的持久化 conversation message。"""

    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(
        min_length=1,
        description="必填字段。单条持久化消息的稳定唯一标识。",
    )
    user_id: str = Field(
        min_length=1,
        description="必填字段。消息所属用户标识，是读取和写入时的隔离边界。",
    )
    session_id: str = Field(
        min_length=1,
        description="必填字段。消息所属会话标识；Storage 不验证对应 session 是否存在。",
    )
    project_id: str | None = Field(
        default=None,
        description="可选字段。消息写入时的项目归属快照，用于直接查询项目对话历史。",
    )
    run_id: str | None = Field(
        default=None,
        description="可选字段。产生或接收该消息的 Agent run 标识；未关联 run 时为 None。",
    )
    role: ConversationMessageRole = Field(
        description="必填字段。消息发送方角色，例如 user、assistant、system 或 tool。",
    )
    content: str = Field(
        min_length=1,
        description="必填字段。用于历史回看的原始或近原始消息正文。",
    )
    content_format: ConversationContentFormat = Field(
        default=ConversationContentFormat.TEXT,
        description="可选字段。消息正文格式，默认 text。",
    )
    created_at: datetime | None = Field(
        default=None,
        description="可选字段。消息创建时间；缺失时由 Store 写入当前 UTC 时间。",
    )
    parent_message_id: str | None = Field(
        default=None,
        description="可选字段。未来分支对话使用的父消息标识；当前不建立外键。",
    )
    metadata_json: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="可选字段。消息级 JSON-safe 扩展信息，不保存内部 prompt 或调试堆栈。",
    )
