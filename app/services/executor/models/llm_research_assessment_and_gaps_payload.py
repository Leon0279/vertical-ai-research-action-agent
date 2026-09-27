"""LLM 完整研究评估决策块的 service-private 输出模型。"""

from pydantic import BaseModel, ConfigDict, Field

from app.services.executor.models.llm_evidence_coverage_entry_payload import (
    LLMEvidenceCoverageEntryPayload,
)
from app.services.executor.models.llm_next_evidence_need_payload import (
    LLMNextEvidenceNeedPayload,
)
from app.services.executor.models.llm_research_assessment_payload import (
    LLMResearchAssessmentPayload,
)
from app.services.executor.models.llm_research_gap_payload import (
    LLMResearchGapPayload,
)


class LLMResearchAssessmentAndGapsPayload(BaseModel):
    """表示大语言模型对研究状态、信息缺口和下一步证据需求的输出。

    Strict LLM output payload for the full 4.4 research decision block.
    """

    model_config = ConfigDict(extra="forbid")

    assessment: LLMResearchAssessmentPayload = Field(
        description=(
            "必填字段。LLM 对当前研究状态的结构化 assessment。"
            "例如：{\"coverage_status\": \"partially_covered\", "
            "\"support_strength\": \"moderate_support\", "
            "\"finding_maturity\": \"partially_stable\", "
            "\"assessment_summary\": \"已有官方说明，"
            "但仍缺少高并发基准数据。\"}。"
        ),
    )
    identified_gaps: list[LLMResearchGapPayload] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。LLM 识别出的多个研究信息缺口。"
            "例如：[{\"gap_scope\": \"sub_question_level\", "
            "\"gap_nature\": \"weak\", \"gap_severity\": \"important\", "
            "\"gap_summary\": \"缺少方案 A 的高并发基准数据。\", "
            "\"gap_target\": \"方案 A 的高并发性能\", "
            "\"gap_actionability\": \"补齐后可判断是否满足峰值流量要求。\"}]。"
        ),
    )
    top_gap: LLMResearchGapPayload = Field(
        description=(
            "必填字段。本轮应优先处理的最高优先级 gap。"
            "例如：{\"gap_scope\": \"sub_question_level\", "
            "\"gap_nature\": \"weak\", \"gap_severity\": \"important\", "
            "\"gap_summary\": \"缺少方案 A 的高并发基准数据。\", "
            "\"gap_target\": \"方案 A 的高并发性能\", "
            "\"gap_actionability\": \"补齐后可判断是否满足峰值流量要求。\"}。"
        ),
    )
    next_evidence_need: LLMNextEvidenceNeedPayload = Field(
        description=(
            "必填字段。由 top gap 推导出的下一轮证据需求。"
            "例如：{\"need_scope\": \"sub_question_level\", "
            "\"need_target\": \"方案 A 的高并发性能\", "
            "\"need_purpose\": \"strengthen_support\", "
            "\"desired_evidence_kind\": \"stronger_supporting_evidence\", "
            "\"freshness_requirement\": \"fresh_preferred\", "
            "\"minimum_support_requirement\": \"moderate_support\", "
            "\"need_summary\": \"查找最近版本的高并发基准数据。\", "
            "\"coverage_target_key\": \"sub_question:1\"}。"
        ),
    )
    evidence_coverage_snapshot: list[LLMEvidenceCoverageEntryPayload] = Field(
        description=(
            "必填字段。覆盖全部受控 target 的本轮全量语义 coverage snapshot。"
            "例如：[{\"target_key\": \"sub_question:1\", "
            "\"coverage_status\": \"partially_covered\", "
            "\"supporting_evidence_keys\": [\"iteration_1:ev_001\"], "
            "\"uncovered_aspects\": [\"缺少公开的高并发基准测试数据\"], "
            "\"coverage_summary\": \"支持并发处理，但性能上限尚未覆盖。\"}]。"
        ),
    )
    prioritization_summary: str = Field(
        min_length=1,
        description=(
            "必填字段。说明为何选定 top gap 与当前 evidence need 的"
            "简短优先级解释。例如：高并发能力直接决定方案 A 是否满足"
            "项目峰值流量要求，因此优先补强该证据。"
        ),
    )
