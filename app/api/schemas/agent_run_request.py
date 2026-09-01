"""Request schemas for agent API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    """表示智能体运行的输入请求。

Single-entry request payload for the run endpoint."""

    query: str = Field(..., min_length=1, description="必填字段。用户提交的原始问题或请求文本，是本次 agent run 的输入。")
    user_id: str = Field(..., min_length=1, description="必填字段。请求所属用户标识，用于运行时隔离与 memory 访问边界。")
    session_id: str | None = Field(default=None, description="可选字段。调用方提供的连续会话标识；缺失时由服务端生成。")
    project_id: str | None = Field(default=None, description="可选字段。请求关联的项目标识，用于加载和写回项目范围 memory。")
    iteration_budget: int = Field(
        default=2,
        ge=1,
        le=5,
        strict=True,
        description="可选字段。当前请求允许执行的最大 research iteration 数量。",
    )
