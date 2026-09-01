"""Request-scoped context model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequestContext(BaseModel):
    """承载请求所需的上下文信息。

Transport-agnostic request context for orchestration."""

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
    iteration_budget: int = Field(
        default=2,
        ge=1,
        le=5,
        strict=True,
        description="可选字段。当前请求允许执行的最大 research iteration 数量。",
    )
