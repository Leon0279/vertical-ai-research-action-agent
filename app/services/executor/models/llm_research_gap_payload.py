"""LLM 研究缺口的 service-private 输出模型。"""

from pydantic import BaseModel, ConfigDict, Field

from app.services.executor.enums import (
    ResearchGapNature,
    ResearchGapScope,
    ResearchGapSeverity,
)


class LLMResearchGapPayload(BaseModel):
    """表示大语言模型研究缺口的内部结构化载荷。

    Service-private schema for one LLM-identified research gap.
    """

    model_config = ConfigDict(extra="forbid")

    gap_scope: ResearchGapScope = Field(
        min_length=1,
        description=(
            "必填字段。信息缺口所在的研究层级或对象范围。"
            "例如：sub_question_level。"
        ),
    )
    gap_nature: ResearchGapNature = Field(
        min_length=1,
        description=(
            "必填字段。缺口的性质，例如缺失、冲突、过期或证据薄弱。"
            "例如：weak。"
        ),
    )
    gap_severity: ResearchGapSeverity = Field(
        min_length=1,
        description=(
            "必填字段。该缺口对当前研究推进的严重程度。"
            "例如：important。"
        ),
    )
    gap_summary: str = Field(
        min_length=1,
        description=(
            "必填字段。对该信息缺口的具体、可理解的说明。"
            "例如：现有材料只说明方案 A 支持并发处理，"
            "未提供高并发场景的性能数据。"
        ),
    )
    gap_target: str | None = Field(
        default=None,
        description=(
            "可选字段。该缺口直接关联的子问题、候选项或研究对象；"
            "无明确目标时为 None。"
            "例如：方案 A 在高并发场景下的性能表现。"
        ),
    )
    gap_actionability: str | None = Field(
        default=None,
        description=(
            "可选字段。补齐该缺口后可支持的决策、比较或行动用途；"
            "不适用时为 None。"
            "例如：补齐后可判断方案 A 是否适合当前项目的峰值流量。"
        ),
    )
