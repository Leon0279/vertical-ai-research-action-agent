"""Research Executor 的 service-private LLM 输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.services.executor.models.research_executor_types import (
    ResearchCoverageStatus,
    ResearchDesiredEvidenceKind,
    ResearchEvidenceGain,
    ResearchFindingMaturity,
    ResearchFindingProgress,
    ResearchFreshnessRequirement,
    ResearchGapNature,
    ResearchGapScope,
    ResearchGapSeverity,
    ResearchIterationOutcome,
    ResearchMinimumSupportRequirement,
    ResearchNeedPurpose,
    ResearchResidualUncertainty,
    ResearchSupportStrength,
    ResearchTopGapProgress,
)

class _LLMResearchAssessmentPayload(BaseModel):
    """表示大语言模型研究评估的内部结构化载荷。

Service-private schema for the LLM's current-state assessment."""

    model_config = ConfigDict(extra="forbid")

    coverage_status: ResearchCoverageStatus = Field(min_length=1, description="必填字段。当前研究目标的证据覆盖状态。")
    support_strength: ResearchSupportStrength = Field(min_length=1, description="必填字段。当前证据对已形成判断的支撑强度。")
    finding_maturity: ResearchFindingMaturity = Field(min_length=1, description="必填字段。当前中间发现的稳定成熟程度。")
    assessment_summary: str = Field(min_length=1, description="必填字段。本轮研究状态评估的简短总结。")


class _LLMResearchGapPayload(BaseModel):
    """表示大语言模型研究缺口的内部结构化载荷。

Service-private schema for one LLM-identified research gap."""

    model_config = ConfigDict(extra="forbid")

    gap_scope: ResearchGapScope = Field(min_length=1, description="必填字段。信息缺口所在的研究层级或对象范围。")
    gap_nature: ResearchGapNature = Field(min_length=1, description="必填字段。缺口的性质，例如缺失、冲突、过期或证据薄弱。")
    gap_severity: ResearchGapSeverity = Field(min_length=1, description="必填字段。该缺口对当前研究推进的严重程度。")
    gap_summary: str = Field(min_length=1, description="必填字段。对该信息缺口的具体、可理解的说明。")
    gap_target: str | None = Field(default=None, description="可选字段。该缺口直接关联的子问题、候选项或研究对象；无明确目标时为 None。")
    gap_actionability: str | None = Field(default=None, description="可选字段。补齐该缺口后可支持的决策、比较或行动用途；不适用时为 None。")


class _LLMNextEvidenceNeedPayload(BaseModel):
    """表示大语言模型下一步证据需求的内部结构化载荷。

Service-private schema for the current iteration's next evidence need."""

    model_config = ConfigDict(extra="forbid")

    need_scope: ResearchGapScope = Field(min_length=1, description="必填字段。下一轮 evidence need 所属的研究范围。")
    need_target: str | None = Field(default=None, description="可选字段。下一轮需要重点补充证据的对象、问题或比较维度。")
    need_purpose: ResearchNeedPurpose = Field(min_length=1, description="必填字段。获取该证据要解决的研究目的。")
    desired_evidence_kind: ResearchDesiredEvidenceKind = Field(min_length=1, description="必填字段。Research Executor 期望获得的证据语义类型。")
    freshness_requirement: ResearchFreshnessRequirement = Field(min_length=1, description="必填字段。该证据对时效性的要求。")
    minimum_support_requirement: ResearchMinimumSupportRequirement = Field(min_length=1, description="必填字段。将缺口视为已推进所需的最低支撑要求。")
    need_summary: str = Field(min_length=1, description="必填字段。下一轮 evidence need 的简短自然语言说明。")
    coverage_target_key: str = Field(
        min_length=1,
        description="必填字段。该 evidence need 对应的 coverage target key，必须来自输入 coverage_targets。",
    )


class _LLMEvidenceCoverageEntryPayload(BaseModel):
    """表示 LLM 对单个 coverage target 的语义覆盖判断。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_key: str = Field(min_length=1, description="必填字段。必须逐字匹配输入 coverage_targets 中的 target_key。")
    coverage_status: ResearchCoverageStatus = Field(description="必填字段。该 target 当前的 evidence 覆盖状态。")
    supporting_evidence_keys: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。经语义判断实际支撑该 target 的 evidence key；只能引用输入 processed_evidence。",
    )
    uncovered_aspects: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。该 target 仍未覆盖、偏弱或需要补强的方面。",
    )
    coverage_summary: str = Field(min_length=1, description="必填字段。该 target 覆盖状态的简短中文说明。")


class _LLMResearchAssessmentAndGapsPayload(BaseModel):
    """表示大语言模型对研究状态、信息缺口和下一步证据需求的结构化输出。

Strict LLM output payload for the full 4.4 research decision block."""

    model_config = ConfigDict(extra="forbid")

    assessment: _LLMResearchAssessmentPayload = Field(description="必填字段。LLM 对当前研究状态的结构化 assessment。")
    identified_gaps: list[_LLMResearchGapPayload] = Field(default_factory=list, description="可选字段，默认空列表。LLM 识别出的多个研究信息缺口。")
    top_gap: _LLMResearchGapPayload = Field(description="必填字段。本轮应优先处理的最高优先级 gap。")
    next_evidence_need: _LLMNextEvidenceNeedPayload = Field(description="必填字段。由 top gap 推导出的下一轮证据需求。")
    evidence_coverage_snapshot: list[_LLMEvidenceCoverageEntryPayload] = Field(
        description="必填字段。覆盖全部受控 target 的本轮全量语义 coverage snapshot。"
    )
    prioritization_summary: str = Field(min_length=1, description="必填字段。说明为何选定 top gap 与当前 evidence need 的简短优先级解释。")


class _LLMIntermediateFindingsPayload(BaseModel):
    """表示大语言模型对中间发现的完整替换结果。

Strict LLM output payload for full intermediate finding replacement."""

    model_config = ConfigDict(extra="forbid")

    intermediate_findings: list[str] = Field(description="必填字段。LLM 返回的全量更新后中间发现列表，而非仅本轮增量。")
    finding_caveats: list[str] = Field(description="必填字段。与当前中间发现对应的全量限制、风险或不确定性说明列表。")


class _LLMIterationOutcomePayload(BaseModel):
    """表示大语言模型对单轮研究迭代结果的结构化判断。

Strict LLM output payload for iteration-end outcome evaluation."""

    model_config = ConfigDict(extra="forbid")

    top_gap_progress: ResearchTopGapProgress = Field(min_length=1, description="必填字段。当前 iteration 对上一轮 top gap 的实际推进程度。")
    evidence_gain: ResearchEvidenceGain = Field(min_length=1, description="必填字段。本轮 acquisition 和 processing 带来的有效证据增益程度。")
    finding_progress: ResearchFindingProgress = Field(min_length=1, description="必填字段。本轮材料对 intermediate findings 的改善或退化情况。")
    residual_uncertainty: ResearchResidualUncertainty = Field(min_length=1, description="必填字段。本轮结束后仍然存在的不确定性水平。")
    proposed_iteration_outcome: ResearchIterationOutcome = Field(min_length=1, description="必填字段。LLM 建议的下一轮控制结果：continue、stop 或 degrade。")
    proposed_outcome_rationale: str = Field(min_length=1, description="必填字段。LLM 提议该 iteration outcome 的简短理由。")
