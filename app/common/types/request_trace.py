"""Request trace model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RequestTrace(BaseModel):
    """记录单次请求在工作流中的追踪信息。

Minimal request-level trace metadata."""

    trace_id: str = Field(description="必填字段。当前请求运行的唯一追踪标识，用于日志关联和问题排查。")
    task_type: str | None = Field(
        default=None,
        description="可选字段。任务理解阶段确定的任务类型文本；尚未解释或不可用时为 None。",
    )
    workflow_pattern: str | None = Field(
        default=None,
        description="可选字段。当前请求采用的 workflow pattern 文本；尚未路由时为 None。",
    )
    planning_depth: str | None = Field(
        default=None,
        description="可选字段。当前 run 采用的 planning depth 文本；未进入规划或未设置时为 None。",
    )
    stage_history: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。已执行 pipeline stage 的名称顺序，用于轻量观测而非保存各 stage 原始输入输出。",
    )
