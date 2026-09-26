"""ResearchStateAssessor 的强类型输入边界。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import FamilyName
from app.domain.models import ContextItem, ProcessedEvidenceUnit, RecentRetrievalAttempt
from app.services.executor.models.evidence_coverage_entry import EvidenceCoverageMap
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMNextEvidenceNeedPayload,
    _LLMResearchGapPayload,
)


class ResearchStateAssessorInput(BaseModel):
    """ResearchStateAssessor 单次评估实际消费的只读状态快照。"""

    model_config = ConfigDict(extra="forbid")

    original_query: str = Field(
        min_length=1,
        description="必填字段。用户原始问题，作为当前研究目标缺失时的兜底语义来源。",
    )
    task_type: str | None = Field(
        description="可空字段。上游识别的任务类型，用于校准 coverage 和 evidence 要求。",
    )
    user_goal: str | None = Field(
        description="可空字段。当前用户目标摘要，优先作为本轮 research objective。",
    )
    task_framing: str | None = Field(
        description="可空字段。当前任务的高层 framing，用于限制研究判断语境。",
    )
    constraints: list[str] = Field(
        description="必填字段。当前研究必须遵守的显式约束快照。",
    )
    project_context_summary: str | None = Field(
        description="可空字段。用于判断 evidence 是否适合当前项目语境的背景摘要。",
    )
    current_bottleneck_summary: str | None = Field(
        description="可空字段。用于校准 gap 优先级的当前关键瓶颈摘要。",
    )
    active_decision_summary: str | None = Field(
        description="可空字段。当前仍生效的关键决策摘要。",
    )
    current_action_status: str | None = Field(
        description="可空字段。当前 action 或执行状态摘要。",
    )
    plan: list[str] = Field(
        description="必填字段。Planning 阶段生成的高层研究推进步骤。",
    )
    sub_questions: list[str] = Field(
        description="必填字段。Planning 阶段拆解出的受控子问题。",
    )
    comparison_candidates: list[str] = Field(
        description="必填字段。Comparison 任务中需要平衡覆盖的候选对象。",
    )
    initial_evidence_strategy: list[str] = Field(
        description="必填字段。Planning 阶段给出的初始 evidence guidance。",
    )
    research_support: list[ContextItem] = Field(
        description="必填字段。进入本轮前已有的研究知识摘要级支持材料。",
    )
    decision_support: list[ContextItem] = Field(
        description="必填字段。进入本轮前已有的决策摘要级支持材料。",
    )
    action_support: list[ContextItem] = Field(
        description="必填字段。进入本轮前已有的行动状态摘要级支持材料。",
    )
    iteration_index: int = Field(
        ge=1,
        description="必填字段。当前 Research Executor iteration 的一开始序号。",
    )
    remaining_iteration_budget: int = Field(
        ge=1,
        description="必填字段。当前轮开始时包含本轮在内的剩余 iteration 数量。",
    )
    latency_budget_ms: int | None = Field(
        description="可空字段。当前 run 的延迟预算，单位为毫秒。",
    )
    available_families: list[FamilyName] = Field(
        description="必填字段。当前 runtime 声明可用于后续 acquisition 的 retrieval families。",
    )
    processed_evidence_units: list[ProcessedEvidenceUnit] = Field(
        description="必填字段。当前 Research Stage 已累计的 typed processed evidence。",
    )
    evidence_coverage_map: EvidenceCoverageMap = Field(
        description="必填字段。进入本轮 assessment 前的完整 typed coverage 状态。",
    )
    intermediate_findings: list[str] = Field(
        description="必填字段。进入本轮 assessment 前已有的全量中间发现。",
    )
    identified_gaps: list[_LLMResearchGapPayload] = Field(
        description="必填字段。上一轮识别出的全部 research gaps；首轮通常为空。",
    )
    top_gap: _LLMResearchGapPayload | None = Field(
        description="可空字段。上一轮选定的最高优先级 gap。",
    )
    next_evidence_need: _LLMNextEvidenceNeedPayload | None = Field(
        description="可空字段。上一轮选定的下一项 evidence need。",
    )
    recent_retrieval_attempts: list[RecentRetrievalAttempt] = Field(
        description="必填字段。本 stage 内已完成的有界压缩检索历史。",
    )
