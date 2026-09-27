"""LLM 单轮研究结果评估的 service-private 输出模型。"""

from pydantic import BaseModel, ConfigDict, Field

from app.services.executor.models.research_executor_types import (
    ResearchEvidenceGain,
    ResearchFindingProgress,
    ResearchIterationOutcome,
    ResearchResidualUncertainty,
    ResearchTopGapProgress,
)


class LLMIterationOutcomePayload(BaseModel):
    """表示大语言模型对单轮研究迭代结果的结构化判断。

    Strict LLM output payload for iteration-end outcome evaluation.
    """

    model_config = ConfigDict(extra="forbid")

    top_gap_progress: ResearchTopGapProgress = Field(
        min_length=1,
        description=(
            "必填字段。当前 iteration 对上一轮 top gap 的实际推进程度。"
            "例如：partially_advanced。"
        ),
    )
    evidence_gain: ResearchEvidenceGain = Field(
        min_length=1,
        description=(
            "必填字段。本轮 acquisition 和 processing 带来的有效证据增益程度。"
            "例如：meaningful_gain。"
        ),
    )
    finding_progress: ResearchFindingProgress = Field(
        min_length=1,
        description=(
            "必填字段。本轮材料对 intermediate findings 的改善或退化情况。"
            "例如：improved_but_not_stable。"
        ),
    )
    residual_uncertainty: ResearchResidualUncertainty = Field(
        min_length=1,
        description=(
            "必填字段。本轮结束后仍然存在的不确定性水平。"
            "例如：moderate。"
        ),
    )
    proposed_iteration_outcome: ResearchIterationOutcome = Field(
        min_length=1,
        description=(
            "必填字段。LLM 建议的下一轮控制结果：continue、stop 或 degrade。"
            "例如：continue。"
        ),
    )
    proposed_outcome_rationale: str = Field(
        min_length=1,
        description=(
            "必填字段。LLM 提议该 iteration outcome 的简短理由。"
            "例如：本轮获得了官方性能说明，但仍缺少独立基准数据，"
            "因此建议继续。"
        ),
    )
