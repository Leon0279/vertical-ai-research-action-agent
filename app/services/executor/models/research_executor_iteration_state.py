"""Research Executor 当前 iteration 的 service-private 状态模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import (
    EvidenceProcessingRequest,
    EvidenceProcessingResult,
    NormalizedRetrievalItem,
    ProcessedEvidenceUnit,
    ToolExecutionLayerRequest,
    ToolExecutionLayerResult,
)
from app.services.executor.models.research_action_request import ResearchActionRequest
from app.services.executor.models.research_executor_types import (
    ResearchActionMode,
    ResearchIterationOutcome,
)
from app.services.executor.models.research_iteration_evaluation_state import (
    ResearchIterationEvaluationState,
)


@dataclass
class ResearchExecutorIterationState:
    """一次 research iteration 的输入、执行产物和最终控制判断。

    每一轮开始时由 ResearchExecutorService 新建，前一轮对象不会被复用；stage-wide
    历史结果和累计 evidence 则保存在 ResearchExecutorRunState。
    """

    iteration_index: int = field(
        metadata={"description": "必填字段。当前 iteration 的一开始计数，最小值为 1。"},
    )
    remaining_iteration_budget: int = field(
        metadata={"description": "必填字段。本轮开始时包含当前轮在内的剩余 iteration 预算。"},
    )
    candidate_action_modes: list[ResearchActionMode] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。规则筛出的本轮可选 action mode。"},
    )
    action_mode: ResearchActionMode | None = field(
        default=None,
        metadata={"description": "可选字段。本轮最终选定的 action mode；action decision 前为空。"},
    )
    action_rationale: str | None = field(
        default=None,
        metadata={"description": "可选字段。系统选择本轮 action mode 的确定性说明。"},
    )
    action_request: ResearchActionRequest | None = field(
        default=None,
        metadata={"description": "可选字段。进入 acquisition 时构造的强类型内部请求；refine 路径为空。"},
    )
    tool_execution_request: ToolExecutionLayerRequest | None = field(
        default=None,
        metadata={"description": "可选字段。本轮实际发送给 Tool Execution Layer 的请求。"},
    )
    tool_execution_result: ToolExecutionLayerResult | None = field(
        default=None,
        metadata={"description": "可选字段。本轮 Tool Execution Layer 的返回结果。"},
    )
    candidate_materials: list[NormalizedRetrievalItem] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。本轮 TEL 返回的候选材料；当前仅用于诊断和后续扩展。"},
    )
    evidence_processing_request: EvidenceProcessingRequest | None = field(
        default=None,
        metadata={"description": "可选字段。本轮发送给 Evidence Processing 的请求。"},
    )
    evidence_processing_result: EvidenceProcessingResult | None = field(
        default=None,
        metadata={"description": "可选字段。本轮 Evidence Processing 的返回结果。"},
    )
    processed_evidence_units: list[ProcessedEvidenceUnit] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。本轮新产生且已加 executor-scoped ID 的 evidence。"},
    )
    evaluation_state: ResearchIterationEvaluationState | None = field(
        default=None,
        metadata={"description": "可选字段。规则短路或 LLM outcome 评估的可解释维度。"},
    )
    proposed_iteration_outcome: ResearchIterationOutcome | None = field(
        default=None,
        metadata={"description": "可选字段。未短路时 LLM 建议的 iteration outcome。"},
    )
    iteration_outcome: ResearchIterationOutcome | None = field(
        default=None,
        metadata={"description": "可选字段。本轮最终确定的 continue、stop 或 degrade 结果。"},
    )
    outcome_rationale: str | None = field(
        default=None,
        metadata={"description": "可选字段。本轮最终 outcome 的说明，可能来自规则或 LLM。"},
    )
    outcome_decision_source: str | None = field(
        default=None,
        metadata={"description": "可选字段。最终 outcome 的来源：rule_short_circuit 或 llm_with_guardrails。"},
    )
    outcome_guardrail_applied: bool = field(
        default=False,
        metadata={"description": "可选字段，默认 False。最终 outcome 是否覆盖了 LLM 原始提议。"},
    )
