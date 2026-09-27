"""ResearchActionDecider 的强类型输出边界。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.services.executor.models.research_action_request import ResearchActionRequest
from app.services.executor.enums import (
    ResearchActionDecisionReason,
    ResearchActionMode,
)


class ResearchActionDeciderOutput(BaseModel):
    """ResearchActionDecider 交还给 Research Executor 的完整规则决策。"""

    model_config = ConfigDict(extra="forbid")

    candidate_action_modes: list[ResearchActionMode] = Field(
        description="必填字段。经过规则 gate 后仍可选择的 action modes。",
    )
    action_mode: ResearchActionMode = Field(
        description="必填字段。本轮最终选定的 action mode。",
    )
    action_decision_reason: ResearchActionDecisionReason = Field(
        description="必填字段。与最终 action mode 对应的稳定规则原因码。",
    )
    action_rationale: str = Field(
        min_length=1,
        description="必填字段。面向日志和诊断的确定性 action 选择说明。",
    )
    acquisition_paths_exhausted: bool = Field(
        description="必填字段。当前 coverage target 的全部兼容 acquisition 路径是否已耗尽。",
    )
    action_request: ResearchActionRequest | None = Field(
        description="可空字段。acquisition 路径的内部强类型请求；refine 路径为 None。",
    )
