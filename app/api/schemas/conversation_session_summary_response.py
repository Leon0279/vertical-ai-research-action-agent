"""Public response schema for one conversation session summary."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ConversationSessionStatus


class ConversationSessionSummaryResponse(BaseModel):
    """返回历史列表展示所需的 session 基本信息。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    session_id: str = Field(min_length=1, description="必填字段。稳定会话标识。")
    project_id: str | None = Field(default=None, description="可选字段。会话所属项目标识。")
    title: str | None = Field(default=None, description="可选字段。会话历史列表标题。")
    session_status: ConversationSessionStatus = Field(description="必填字段。会话生命周期状态。")
    created_at: datetime = Field(description="必填字段。会话创建时间。")
    updated_at: datetime = Field(description="必填字段。会话最近更新时间。")
    last_message_at: datetime | None = Field(default=None, description="可选字段。最近一条消息的创建时间。")
