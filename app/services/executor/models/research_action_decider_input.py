"""ResearchActionDecider 的强类型输入边界。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import FamilyName
from app.domain.models import RecentRetrievalAttempt
from app.services.executor.models.llm_next_evidence_need_payload import (
    LLMNextEvidenceNeedPayload,
)
from app.services.executor.models.llm_research_assessment_payload import (
    LLMResearchAssessmentPayload,
)
from app.services.executor.models.llm_research_gap_payload import (
    LLMResearchGapPayload,
)


class ResearchActionDeciderInput(BaseModel):
    """ResearchActionDecider 单次规则判断实际消费的只读状态快照。"""

    model_config = ConfigDict(extra="forbid")

    original_query: str = Field(
        min_length=1,
        description="必填字段。用户原始问题，作为 action target problem 的最终兜底。",
    )
    user_goal: str | None = Field(
        description="可空字段。当前用户目标摘要，可作为 action target problem 的语义来源。",
    )
    available_families: list[FamilyName] = Field(
        description="必填字段。当前 runtime 声明可用于 acquisition 的 retrieval families。",
    )
    latency_budget_ms: int | None = Field(
        description="可空字段。当前 run 的延迟预算，单位为毫秒。",
    )
    scope_restrictions: list[str] = Field(
        description="必填字段。需要随 acquisition action request 传递的访问或行动范围限制。",
    )
    current_assessment: LLMResearchAssessmentPayload = Field(
        description="必填字段。Step 1 对当前 coverage、support 和 finding maturity 的判断。",
    )
    top_gap: LLMResearchGapPayload = Field(
        description="必填字段。Step 1 选定的最高优先级 research gap。",
    )
    next_evidence_need: LLMNextEvidenceNeedPayload = Field(
        description="必填字段。Step 1 根据 top gap 选定的下一项 evidence need。",
    )
    recent_retrieval_attempts: list[RecentRetrievalAttempt] = Field(
        description="必填字段。本 Research Stage 内可用于规避低价值路径的近期检索历史。",
    )
    iteration_index: int = Field(
        ge=1,
        description="必填字段。当前 Research Executor iteration 的一开始序号。",
    )
    remaining_iteration_budget: int = Field(
        ge=0,
        description="必填字段。当前轮开始时的剩余 iteration 预算；允许为零以支持防御性收束。",
    )
