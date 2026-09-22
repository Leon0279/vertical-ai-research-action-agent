"""Stable error response schema for conversation history APIs."""

from pydantic import BaseModel, ConfigDict, Field


class ConversationHistoryErrorResponse(BaseModel):
    """表示 conversation history 查询未成功完成时的稳定错误响应。"""

    model_config = ConfigDict(extra="forbid")

    error_code: str = Field(min_length=1, description="必填字段。供客户端判断错误类别的机器可读错误码。")
    error_reason: str = Field(min_length=1, description="必填字段。可安全展示或记录且不包含底层存储细节的错误原因。")
