"""Tool Execution Layer 单次 attempt 的内部结果容器。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import (
    BaseFamilyExecutionResult,
    RequestCompletionEvaluationResult,
    RetrievalQueryGenerationResult,
)


@dataclass
class ToolExecutionLayerAttemptOutcome:
    """ToolExecutionLayerService 内部一次 attempt 的可变结果包。

    该类只服务于 `ToolExecutionLayerService.execute(...)` 的内部流程拆分，用来把
    “选择 family -> 生成 query -> 执行 family -> 生成 evaluation” 这一次 attempt
    的中间产物集中传递。它不是 domain model，不是 public API，也不应该被
    Research Executor、family service 或其它 component 直接依赖。
    """

    selected_family: str | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。本次 attempt 选中的 retrieval family，例如 docs_search、paper_search、"
                "web_search、research_knowledge_recall。当前只由 ToolExecutionLayerService 内部写入和读取；"
                "selection 失败或 attempt 尚未准备完成时为空。"
            ),
        },
    )
    query_generation_result: RetrievalQueryGenerationResult | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。本次 attempt 对应的 query generation 结果。当前只由 ToolExecutionLayerService 内部使用；"
                "retry_same_tool 时会复用上一轮的 query_generation_result，避免重新生成 query。"
            ),
        },
    )
    family_result: BaseFamilyExecutionResult | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。本次 attempt 执行 selected family 后得到的 family execution result。"
                "family 尚未执行、family service 缺失、query generation 失败等提前失败路径中为空；"
                "如果 family service 抛异常，ToolExecutionLayerService 会合成 failed family result 并写入这里。"
            ),
        },
    )
    evaluation_result: RequestCompletionEvaluationResult | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。本次 attempt 的 completion / recovery evaluation 结果。当前只由 "
                "ToolExecutionLayerService 内部用于判断 stop、retry_same_tool、fallback 或不可执行 recovery。"
                "如果 attempt 在 evaluation 前失败，则为空。"
            ),
        },
    )
    execution_failure_reason: str | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。family execution 阶段失败原因的内部归一化标记。当前主要在 family service "
                "抛异常时设置为 tool_error，并传给 RequestCompletionEvaluationService；正常执行或提前失败时为空。"
            ),
        },
    )
    error_info: str | None = field(
        default=None,
        metadata={
            "description": (
                "可选字段。本次 attempt 的内部失败摘要。当前由 ToolExecutionLayerService 用来判断是否应直接返回 failed result；"
                "例如 family selection no_match、query generation failed、缺少 family service、memory 缺 owner_user_id、"
                "evaluation failed 等。该字段不是最终用户输出，只会被聚合进 ToolExecutionLayerResult.error_info。"
            ),
        },
    )
