"""Research Executor 内部的 iteration outcome 评估状态模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.executor.models.research_executor_types import (
    ResearchEvidenceGain,
    ResearchFindingProgress,
    ResearchResidualUncertainty,
    ResearchTopGapProgress,
)


@dataclass
class ResearchIterationEvaluationState:
    """记录当前 iteration 的规则短路或 LLM 评估维度。

    该模型只保留 outcome decision 的可解释输入，不直接表达最终 continue、stop
    或 degrade；最终控制结果由 ResearchExecutorIterationState 单独保存。
    """

    short_circuit_reason: str | None = field(
        default=None,
        metadata={"description": "可选字段。规则短路时使用的原因；未短路时为空。"},
    )
    top_gap_progress: ResearchTopGapProgress | None = field(
        default=None,
        metadata={"description": "可选字段。LLM 对当前 top gap 推进程度的判断。"},
    )
    evidence_gain: ResearchEvidenceGain | None = field(
        default=None,
        metadata={"description": "可选字段。LLM 对本轮有效 evidence 增益的判断。"},
    )
    finding_progress: ResearchFindingProgress | None = field(
        default=None,
        metadata={"description": "可选字段。LLM 对 intermediate findings 变化的判断。"},
    )
    residual_uncertainty: ResearchResidualUncertainty | None = field(
        default=None,
        metadata={"description": "可选字段。LLM 判断的本轮结束后剩余不确定性。"},
    )
