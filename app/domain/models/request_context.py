"""Request-scoped context model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequestContext(BaseModel):
    """Transport-agnostic request context for orchestration."""

    original_query: str = Field(description="必填字段。用户提交的原始请求文本，供 request intake 初始化当前 run。")
    user_id: str = Field(min_length=1, description="必填字段。请求所属用户标识，用于权限隔离和 memory 边界。")
    session_id: str | None = Field(
        default=None,
        description="可选字段。调用方提供的会话标识；缺失时由 request intake 生成新的 session id。",
    )
    project_id: str | None = Field(
        default=None,
        description="可选字段。请求关联的项目范围标识；没有项目上下文时为 None。",
    )
