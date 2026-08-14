"""Domain model for request completion and recovery evaluation results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EvaluationStatus = Literal["evaluated", "failed"]
RequestCompletionStatus = Literal[
    "complete",
    "incomplete_recoverable",
    "incomplete_unrecoverable",
]
RecoveryAction = Literal["continue", "retry_same_tool", "fallback", "stop"]
NextStepHint = Literal[
    "none",
    "continue_current_request",
    "retry_same_tool",
    "fallback_within_same_family",
    "fallback_to_broader_search",
    "stop_request",
]


class RequestCompletionEvaluationResult(BaseModel):
    """表示请求完成度评估的处理结果。

Output of evaluating request completion and recovery need."""

    evaluation_status: EvaluationStatus = Field(
        description="必填字段。evaluation 是否成功完成，或因输入/内部异常而失败。",
    )
    request_completion_status: RequestCompletionStatus | None = Field(
        default=None,
        description="可选字段。当前请求是 complete、可恢复未完成还是不可恢复未完成；evaluation 失败时为 None。",
    )
    request_completed: bool = Field(
        description="当前请求是否应被视为完成，用于 TEL 控制是否继续 attempt。",
    )
    needs_recovery: bool = Field(
        description="下游 orchestration 是否应考虑 retry 或 fallback 等恢复路径。",
    )
    recovery_action: RecoveryAction | None = Field(
        default=None,
        description="可选字段。最小恢复动作信号，不是直接执行命令；没有恢复需求时为 None。",
    )
    recovery_reason: str | None = Field(
        default=None,
        description="可选字段。对恢复或停止决策的人类可读说明；没有说明时为 None。",
    )
    next_step_hint: NextStepHint | None = Field(
        default=None,
        description="可选字段。供 ToolExecutionLayerService 解释下一步处理的紧凑提示。",
    )
    evaluation_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="可选字段，默认空字典。evaluation outcome 与策略判断的紧凑摘要；仅放稳定观测信息。",
    )
    evaluation_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="可选字段，默认空字典。归一化输入与 recovery 可用性计算过程的 trace，用于调试与观测。",
    )
    error_info: str | None = Field(
        default=None,
        description="可选字段。当 evaluation_status 为 failed 时的顶层失败说明；成功时为 None。",
    )
