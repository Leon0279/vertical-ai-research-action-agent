"""Stable error response for Memory query APIs."""

from pydantic import BaseModel, ConfigDict, Field


class MemoryQueryErrorResponse(BaseModel):
    """Memory 查询接口对外暴露的安全错误结构。"""

    model_config = ConfigDict(extra="forbid")

    error_code: str = Field(min_length=1)
    error_reason: str = Field(min_length=1)
