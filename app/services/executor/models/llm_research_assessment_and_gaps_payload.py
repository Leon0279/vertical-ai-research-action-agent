"""LLM 完整研究评估与下一步行动的 service-private 输出模型。"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import FamilyName
from app.services.executor.enums import ResearchActionMode

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
    action_mode: ResearchActionMode = Field(
        description=(
            "必填字段。当前轮在利用现有状态、回忆研究记忆或外部检索之间选择的"
            "高层推进方式。例如：\"external_acquisition\"。"
        ),
    )
    preferred_family: FamilyName | None = Field(
        default=None,
        description=(
            "可空字段。需要 acquisition 时建议 TEL 优先选择的 retrieval family；"
            "refine 时必须为 null。例如：\"docs_search\"。"
        ),
    )
    retrieval_query: str | None = Field(
        default=None,
        description=(
            "可空字段。需要 acquisition 时交给 TEL 复用的非空检索短语；"
            "refine 时必须为 null。例如：\"FastAPI lifespan dependency injection official docs\"。"
        ),
    )
    action_rationale: str = Field(
        min_length=1,
        description=(
            "必填字段。说明为何选择当前 action mode 与 preferred family 的简短理由。"
            "例如：当前缺口需要官方实现说明，因此优先检索官方文档。"
        ),
    )

    @model_validator(mode="after")
    def validate_action_contract(self) -> "LLMResearchAssessmentAndGapsPayload":
        """校验 action mode、family 和 query 的结构一致性。"""

        query = (self.retrieval_query or "").strip() or None
        self.retrieval_query = query
        if self.action_mode == ResearchActionMode.REFINE_FROM_EXISTING_STATE:
            if self.preferred_family is not None or query is not None:
                raise ValueError(
                    "refine_from_existing_state requires null preferred_family and retrieval_query."
                )
            return self

        if query is None:
            raise ValueError("Acquisition action modes require a non-empty retrieval_query.")
        if self.action_mode == ResearchActionMode.MEMORY_BACKED_ACQUISITION:
            if self.preferred_family != FamilyName.RESEARCH_KNOWLEDGE_RECALL:
                raise ValueError(
                    "memory_backed_acquisition requires research_knowledge_recall."
                )
            return self

        if self.preferred_family not in {
            FamilyName.DOCS_SEARCH,
            FamilyName.PAPER_SEARCH,
            FamilyName.WEB_SEARCH,
        }:
            raise ValueError(
                "external_acquisition requires docs_search, paper_search, or web_search."
            )
        return self
