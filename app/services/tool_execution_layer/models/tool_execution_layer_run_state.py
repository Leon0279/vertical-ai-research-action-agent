"""Tool Execution Layer 单次 execute 调用的内部运行状态容器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.models import (
    BaseFamilyExecutionResult,
    FamilySelectionResult,
    RequestCompletionEvaluationResult,
    RetrievalQueryGenerationResult,
)


@dataclass
class ToolExecutionLayerRunState:
    """ToolExecutionLayerService.execute(...) 内部使用的可变运行状态。

    该类只表示一次 ToolExecutionLayerService.execute 调用期间的 service-local state，
    用于把 retry / fallback / latest result / attempt trace 等可变信息集中管理。
    它不是全局运行状态模型，不是 execution context，也不是 domain/public contract；
    不应被 Tool Execution Layer 之外的组件直接依赖。
    """

    blocked_families: list[str] = field(
        metadata={
            "description": (
                "必填字段。本次 TEL request 内当前禁止再次选择的 family 列表。初始值来自 "
                "ToolExecutionLayerRequest.blocked_source_families；当 evaluator 要求 fallback_to_broader_search "
                "时，ToolExecutionLayerService 会把当前 selected_family 追加到这里，避免 fallback 又选回同一个 family。"
            ),
        },
    )
    attempts: list[dict[str, Any]] = field(
        default_factory=list,
        metadata={
            "description": (
                "可选字段，默认空列表。当前 execute 调用内已经完成 evaluation 的 attempt trace 列表。"
                "每个 dict 来自 ToolExecutionLayerService._attempt_trace(...)，当前包含 selected_family、generated_query、"
                "query_focus、acquisition_status、evaluation_status、recovery_action、next_step_hint、retry_count、"
                "fallback_applied 等 key。最终会写入 ToolExecutionLayerResult.retrieval_trace.attempts。"
            ),
        },
    )
    latest_selection: FamilySelectionResult | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。最近一次 family selection 的结果。当前用于失败/完成 result 汇总："
                "如果后续 query generation、family execution 或 evaluation 出错，ToolExecutionLayerService 会把它传给 "
                "result builder 以保留 selection summary。retry_same_tool 不会更新该字段，因为 retry 不重新选择 family。"
            ),
        },
    )
    latest_query_generation: RetrievalQueryGenerationResult | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。最近一次 query generation 的结果。当前用于失败/完成 result 汇总和 trace 补充。"
                "retry_same_tool 会复用原 query_generation_result，不重新生成 query；fallback_to_broader_search 会为新 family "
                "重新生成 query 并更新该字段。"
            ),
        },
    )
    latest_family_result: BaseFamilyExecutionResult | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。最近一次 family execution 的结果。当前用于构造最终 ToolExecutionLayerResult 的 normalized_items、"
                "acquisition_status、source_summary、execution_summary 和 retrieval_trace。family 尚未执行就失败时为空；"
                "family service 抛异常时会写入合成的 failed family result。"
            ),
        },
    )
    latest_evaluation: RequestCompletionEvaluationResult | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。最近一次 completion / recovery evaluation 的结果。当前用于最终 execution_summary / retrieval_trace 汇总，"
                "并驱动 retry、fallback、stop 或 recovery unavailable 的决策。attempt 在 evaluation 前失败时为空。"
            ),
        },
    )
    retry_count: int = field(
        default=0,
        metadata={
            "description": (
                "可选字段，默认 0。本次 TEL request 内已经执行的 retry_same_tool 次数。当前由 "
                "ToolExecutionLayerService._apply_evaluation_result(...) 在 retry 真正被安排前递增；最终会写入 "
                "ToolExecutionLayerResult.execution_summary.retry_count。"
            ),
        },
    )
    fallback_applied: bool = field(
        default=False,
        metadata={
            "description": (
                "可选字段，默认 False。本次 TEL request 内是否已经执行过 broader-family fallback。当前用于保证 "
                "fallback_to_broader_search 只执行一次；第二次遇到 broader fallback 会停止并记录 "
                "recovery_exhausted_reason=fallback_already_applied。"
            ),
        },
    )
    recovery_attempt_count: int = field(
        default=0,
        metadata={
            "description": (
                "可选字段，默认 0。本次 TEL request 内已经实际安排的 recovery attempt 数量，包括 retry_same_tool "
                "和 fallback_to_broader_search。当前用于 final execution_summary 的观测统计，不代表 family execution 总次数。"
            ),
        },
    )
    recovery_exhausted_reason: str | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。TEL 停止继续执行 evaluator 给出的 recovery signal 的原因。当前可能值包括 "
                "retry_budget_exhausted、fallback_already_applied、same_family_fallback_not_executable、"
                "continuation_not_supported、recovery_action_not_executable。为空表示没有特殊 recovery exhaustion。"
            ),
        },
    )
    retry_context: tuple[str, RetrievalQueryGenerationResult] | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。下一轮 retry_same_tool 需要复用的上下文，结构为 (selected_family, query_generation_result)。"
                "当前只在 evaluator 返回 retry_same_tool 且 retry budget 允许时设置；下一轮 attempt 会直接消费它，"
                "从而跳过 family selection 和 query generation，并保持原始 generated_query / preferred_tool 语义不变。"
            ),
        },
    )
