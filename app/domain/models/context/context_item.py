"""Supporting context item retained outside core running state."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextItem(BaseModel):
    """表示可注入执行上下文的单条信息。

Selected supporting context retained outside core running state."""

    id: str = Field(
        min_length=1,
        description="必填字段。当前已筛选 supporting context item 的稳定标识，用于去重和关联。",
    )
    source_type: str = Field(
        min_length=1,
        description=(
            "必填字段。该 context item 的来源类别，例如 session_memory、project_profile、"
            "decision_memory、research_memory 或 tool_result。"
        ),
    )
    scope_id: str | None = Field(
        default=None,
        description="可选字段。该 supporting context item 关联的 scope 标识，例如项目或用户范围；没有时为 None。",
    )
    summary: str = Field(
        min_length=1,
        description=(
            "必填字段。可直接供 planning、research 或 conclusion 使用的摘要级内容。"
            "它应保持简洁，不能默认存放大段原始 payload。"
        ),
    )
    priority: int = Field(
        description="必填字段。在上下文预算受限时用于选择或保留该 supporting context item 的优先级信号。",
    )
    freshness_tag: str | None = Field(
        default=None,
        description="可选字段。该 context item 的新鲜度标签，例如 fresh、aging 或 stale；无评估时为 None。",
    )
    confidence: str | None = Field(
        default=None,
        description="可选字段。该 context item 的置信度标签，例如 low、medium 或 high；未提供时为 None。",
    )
    can_assimilate_to_state: bool = Field(
        default=False,
        description="该 supporting item 在成为当前 run 核心上下文后，是否适合被吸收到 RunningState。",
    )
    usage_hint: str | None = Field(
        default=None,
        description=(
            "可选字段。说明该 item 最适合在哪个阶段使用的提示，例如 planning_only、"
            "research_support 或 conclusion_support。"
        ),
    )
