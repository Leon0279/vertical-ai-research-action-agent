"""ResearchMaterialAcquirer.acquire 的强类型输入边界。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import FamilyName
from app.domain.models import RecentRetrievalAttempt
from app.services.executor.enums import ResearchActionMode
from app.services.executor.models.llm_next_evidence_need_payload import (
    LLMNextEvidenceNeedPayload,
)
from app.services.executor.models.llm_research_gap_payload import (
    LLMResearchGapPayload,
)


class ResearchMaterialAcquireInput(BaseModel):
    """单次 Research Material Acquisition 实际消费的只读状态快照。"""

    model_config = ConfigDict(extra="forbid")

    original_query: str = Field(
        min_length=1,
        description=(
            "必填字段。用户原始问题，作为 TEL target problem 的最终兜底。"
        ),
    )
    user_goal: str | None = Field(
        description=(
            "可空字段。当前用户目标摘要，可作为 TEL target problem 的语义来源。"
        ),
    )
    task_framing: str | None = Field(
        description="可空字段。当前任务 framing，将原样投影到 TEL request。",
    )
    owner_user_id: str | None = Field(
        description="可空字段。memory-backed acquisition 使用的用户所有权边界。",
    )
    project_scope_id: str | None = Field(
        description="可空字段。memory-backed acquisition 使用的项目范围边界。",
    )
    latency_budget_ms: int | None = Field(
        description="可空字段。传递给 TEL 的超时预算，单位为毫秒。",
    )
    iteration_index: int = Field(
        ge=1,
        description="必填字段。当前 Research Executor iteration 从 1 开始的序号。",
    )
    action_mode: ResearchActionMode = Field(
        description="必填字段。Assessor 选定的 acquisition action mode。",
    )
    preferred_family: FamilyName = Field(
        description="必填字段。Assessor 建议 TEL 优先选择的 retrieval family。",
    )
    retrieval_query: str = Field(
        min_length=1,
        description="必填字段。Assessor 生成并由 TEL 直接复用的检索短语。",
    )
    available_families: list[FamilyName] = Field(
        description="必填字段。当前 runtime 真正可用的 retrieval family 快照。",
    )
    top_gap: LLMResearchGapPayload = Field(
        description="必填字段。触发本轮 acquisition 的最高优先级研究缺口。",
    )
    next_evidence_need: LLMNextEvidenceNeedPayload = Field(
        description="必填字段。本轮 acquisition 要满足的证据需求。",
    )
    recent_retrieval_attempts: list[RecentRetrievalAttempt] = Field(
        description=(
            "必填字段。本 Research Stage 内可用于 TEL 避免低价值重复检索的近期历史。"
        ),
    )
