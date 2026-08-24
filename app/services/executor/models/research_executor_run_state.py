"""Research Executor 单次 execute 调用的 service-private 运行状态模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import (
    EvidenceProcessingResult,
    ProcessedEvidenceUnit,
    RecentRetrievalAttempt,
    ToolExecutionLayerResult,
)
from app.services.executor.models.evidence_coverage_entry import EvidenceCoverageMap
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMNextEvidenceNeedPayload,
    _LLMResearchAssessmentPayload,
    _LLMResearchGapPayload,
)


@dataclass
class ResearchExecutorRunState:
    """一次 ResearchExecutorService.execute(...) 内跨 iteration 累积的可变状态。

    它不是 ExecutionContext、ResearchStageResult、domain model 或 public contract。所有
    executor-private collaborator 只能通过该模型读写 stage-local 状态，不能再依赖裸 dict key。
    """

    evidence_coverage_map: EvidenceCoverageMap = field(
        metadata={"description": "必填字段。由 ResearchCoverageTracker 初始化并持续维护的目标覆盖状态。"},
    )
    processed_evidence_units: list[ProcessedEvidenceUnit] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。本 stage 累积的全部 typed processed evidence。"},
    )
    current_assessment: _LLMResearchAssessmentPayload | None = field(
        default=None,
        metadata={"description": "可选字段。最近一次 assessment LLM 的当前研究状态判断。"},
    )
    identified_gaps: list[_LLMResearchGapPayload] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。最近一次 assessment 识别出的全部 research gaps。"},
    )
    top_gap: _LLMResearchGapPayload | None = field(
        default=None,
        metadata={"description": "可选字段。最近一次 assessment 选出的最高优先级 gap。"},
    )
    next_evidence_need: _LLMNextEvidenceNeedPayload | None = field(
        default=None,
        metadata={"description": "可选字段。最近一次 assessment 选定的下一项 evidence need。"},
    )
    prioritization_summary: str | None = field(
        default=None,
        metadata={"description": "可选字段。最近一次 top gap 与 evidence need 的优先级说明。"},
    )
    intermediate_findings: list[str] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。本 stage 的全量中间发现。"},
    )
    finding_caveats: list[str] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。与当前 intermediate findings 对应的限制说明。"},
    )
    recent_retrieval_attempts: list[RecentRetrievalAttempt] = field(
        default_factory=list,
        metadata={
            "description": (
                "可选字段，默认空列表。本 stage 内已经完成、可供下一轮路径规避使用的压缩检索历史；"
                "不保存 raw trace，不进入 RunningState、Memory 或 ResearchStageResult。"
            )
        },
    )
    tool_execution_results: list[ToolExecutionLayerResult] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。本 stage 每轮实际执行过的 TEL result 历史。"},
    )
    evidence_processing_results: list[EvidenceProcessingResult] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。本 stage 每轮实际执行过的 Evidence Processing result 历史。"},
    )
    current_iteration: ResearchExecutorIterationState | None = field(
        default=None,
        metadata={"description": "可选字段。当前正在执行或最近完成的 iteration state。"},
    )

    def require_current_iteration(self) -> ResearchExecutorIterationState:
        """返回当前 iteration state；尚未初始化时抛出内部状态错误。"""

        if self.current_iteration is None:
            raise ValueError("current_iteration is required for this research step.")
        return self.current_iteration
