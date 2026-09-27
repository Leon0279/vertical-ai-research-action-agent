"""LLM 下一步证据需求的 service-private 输出模型。"""

from pydantic import BaseModel, ConfigDict, Field

from app.services.executor.enums import (
    ResearchDesiredEvidenceKind,
    ResearchFreshnessRequirement,
    ResearchGapScope,
    ResearchMinimumSupportRequirement,
    ResearchNeedPurpose,
)


class LLMNextEvidenceNeedPayload(BaseModel):
    """表示大语言模型下一步证据需求的内部结构化载荷。

    Service-private schema for the current iteration's next evidence need.
    """

    model_config = ConfigDict(extra="forbid")

    need_scope: ResearchGapScope = Field(
        min_length=1,
        description=(
            "必填字段。下一轮 evidence need 所属的研究范围。"
            "例如：sub_question_level。"
        ),
    )
    need_target: str | None = Field(
        default=None,
        description=(
            "可选字段。下一轮需要重点补充证据的对象、问题或比较维度。"
            "例如：方案 A 在高并发场景下的性能表现。"
        ),
    )
    need_purpose: ResearchNeedPurpose = Field(
        min_length=1,
        description=(
            "必填字段。获取该证据要解决的研究目的。"
            "例如：strengthen_support。"
        ),
    )
    desired_evidence_kind: ResearchDesiredEvidenceKind = Field(
        min_length=1,
        description=(
            "必填字段。Research Executor 期望获得的证据语义类型。"
            "例如：stronger_supporting_evidence。"
        ),
    )
    freshness_requirement: ResearchFreshnessRequirement = Field(
        min_length=1,
        description="必填字段。该证据对时效性的要求。例如：fresh_preferred。",
    )
    minimum_support_requirement: ResearchMinimumSupportRequirement = Field(
        min_length=1,
        description=(
            "必填字段。将缺口视为已推进所需的最低支撑要求。"
            "例如：moderate_support。"
        ),
    )
    need_summary: str = Field(
        min_length=1,
        description=(
            "必填字段。下一轮 evidence need 的简短自然语言说明。"
            "例如：查找方案 A 最近版本的高并发基准测试或官方性能说明。"
        ),
    )
    coverage_target_key: str = Field(
        min_length=1,
        description=(
            "必填字段。该 evidence need 对应的 coverage target key，"
            "必须来自输入 coverage_targets。"
            "例如：sub_question:1。"
        ),
    )
