"""API schema for action items."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ActionItemSchema(BaseModel):
    """User-facing action item structure."""

    title: str = Field(description="必填字段。向 API 调用方展示的行动项标题，说明用户下一步可执行的事项。")
    description: str | None = Field(
        default=None,
        description="可选字段。行动项的执行说明、前置条件或预期结果；没有补充时为 None。",
    )
    priority: str = Field(
        default="medium",
        description="行动项优先级标签。当前默认 medium，供客户端排序或突出展示使用。",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="可选字段，默认空字典。行动项的扩展展示信息；不包含原始工具响应或内部调试数据。",
    )
