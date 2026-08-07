"""Response schemas for agent API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.action_item_schema import ActionItemSchema
from app.api.schemas.citation_schema import CitationSchema


class AgentRunResponse(BaseModel):
    """Single-entry response payload for the run endpoint."""

    trace_id: str | None = Field(default=None, description="可选字段。当前请求的 trace id。")
    task_type: str = Field(description="必填字段。当前请求的任务类型。")
    workflow_pattern: str = Field(description="必填字段。当前请求实际采用的 workflow pattern。")
    answer: str = Field(description="必填字段。最终给用户阅读的完整自然语言答案。")
    summary: str = Field(description="必填字段。最终答案的短摘要或预览文案。")
    recommendation: str | None = Field(default=None, description="可选字段。结构化主推荐、主判断或主结论短句。")
    action_items: list[ActionItemSchema] = Field(default_factory=list, description="可选字段，默认空列表。结构化行动项。")
    citations: list[CitationSchema] = Field(default_factory=list, description="可选字段，默认空列表。最终答案引用的来源。")
    confidence: float | None = Field(default=None, description="可选字段。最终答案整体置信度分数。")
    caveats: list[str] = Field(default_factory=list, description="可选字段，默认空列表。最终答案的限制、风险或未解决问题。")
    stage_history: list[str] = Field(default_factory=list, description="可选字段，默认空列表。本次 run 执行过的 stage。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="可选字段，默认空 dict。最终响应的轻量运行 metadata。")
