"""Versioned opaque cursor payload for conversation history queries."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConversationPageCursor(BaseModel):
    """表示 conversation history keyset 分页位置的内部结构。"""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = Field(
        default=1,
        description="必填字段。Cursor wire format 版本，当前固定为 1。",
    )
    collection: Literal["sessions", "messages"] = Field(
        description="必填字段。Cursor 所属集合，防止 session 与 message cursor 混用。",
    )
    position_at: datetime = Field(
        description="必填字段。Session 使用 updated_at，message 使用 created_at 的分页位置时间。",
    )
    position_id: str = Field(
        min_length=1,
        description="必填字段。与位置时间共同形成稳定排序的 session_id 或 message_id。",
    )
    session_id: str | None = Field(
        default=None,
        description="可选字段。Message cursor 必须绑定的会话标识；session 列表 cursor 为 None。",
    )

    @field_validator("position_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """要求分页位置时间携带时区，避免排序含义不明确。

        Args:
            value (datetime): 待校验的分页位置时间。

        Returns:
            datetime: 已确认包含时区的原始时间值。
        """

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("position_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_collection_scope(self) -> "ConversationPageCursor":
        """确保 message cursor 绑定 session，session cursor 不携带多余作用域。

        Returns:
            ConversationPageCursor: 已完成 collection-specific scope 校验的 cursor。
        """

        if self.collection == "messages":
            if self.session_id is None or not self.session_id.strip():
                raise ValueError("message cursors require session_id")
            return self
        if self.session_id is not None:
            raise ValueError("session cursors cannot contain session_id")
        return self
