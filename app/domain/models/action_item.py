"""Domain model for action items."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    """Actionable next step."""

    title: str = Field(description="必填字段。面向用户或下游任务系统展示的行动项标题，应简洁说明下一步要做什么。")
    description: str | None = Field(
        default=None,
        description="可选字段。对行动项执行范围、前置条件或预期产出的补充说明；没有额外说明时为 None。",
    )
    priority: str = Field(
        default="medium",
        description="行动项优先级标签。当前默认值为 medium，供输出展示或未来任务排序使用。",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="可选字段，默认空字典。行动项的非核心扩展信息；当前没有稳定公共 key，不能放入原始工具响应或调试数据。",
    )
