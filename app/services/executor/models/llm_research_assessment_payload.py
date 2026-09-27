"""LLM 研究状态评估的 service-private 输出模型。"""

from pydantic import BaseModel, ConfigDict, Field

from app.services.executor.models.research_executor_types import (
    ResearchCoverageStatus,
    ResearchFindingMaturity,
    ResearchSupportStrength,
)


class LLMResearchAssessmentPayload(BaseModel):
    """表示大语言模型研究评估的内部结构化载荷。

    Service-private schema for the LLM's current-state assessment.
    """

    model_config = ConfigDict(extra="forbid")

    coverage_status: ResearchCoverageStatus = Field(
        min_length=1,
        description=(
            "必填字段。当前研究目标的证据覆盖状态。"
            "例如：partially_covered。"
        ),
    )
    support_strength: ResearchSupportStrength = Field(
        min_length=1,
        description=(
            "必填字段。当前证据对已形成判断的支撑强度；"
            "moderate_support 表示已有实质支撑，"
            "但尚未达到 strong_enough。例如：moderate_support。"
        ),
    )
    finding_maturity: ResearchFindingMaturity = Field(
        min_length=1,
        description=(
            "必填字段。当前中间发现的稳定成熟程度。"
            "例如：partially_stable。"
        ),
    )
    assessment_summary: str = Field(
        min_length=1,
        description=(
            "必填字段。本轮研究状态评估的简短总结。"
            "例如：已获得官方文档支持，但仍缺少方案 A 的"
            "高并发基准数据。"
        ),
    )
