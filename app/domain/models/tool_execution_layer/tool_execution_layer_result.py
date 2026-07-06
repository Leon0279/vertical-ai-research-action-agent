"""Tool Execution Layer result 的 domain model。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import AcquisitionStatus
from app.domain.models.retrieval import (
    NormalizedRetrievalItem,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)
from app.domain.models.tool_execution_layer.tool_execution_layer_request import (
    ExecutionStatus,
)


class ToolExecutionLayerResult(BaseModel):
    """Tool Execution Layer 单次 request 的稳定输出。

    该模型面向 Research Executor 和后续 EvidenceProcessingService。它表达的是“本次 TEL
    retrieval/tool execution 最终拿到了什么候选材料，以及执行是否完成/失败”，而不是 TEL 内部
    子 service 的完整中间对象。TEL 顶层不负责 selected_tool，因此 result 顶层也不暴露 selected_tool；
    若需要 provenance，可从 source_summary / retrieval_trace 中读取 family/tool 层保留的信息。
    """

    execution_status: ExecutionStatus = Field(
        description=(
            "必填字段。TEL flow 的最终执行状态。当前项目中有用：Research Executor 可以用它判断本次 "
            "tool execution layer request 是否完成到可交给 EvidenceProcessing 的程度。completed 表示 TEL 已经完成一轮 "
            "bounded request flow，可能包含 retry/fallback；failed 表示在 family selection、query generation、family execution "
            "前置校验或 evaluation 等阶段发生不可继续的失败。该字段不是 acquisition_status，不能替代具体检索结果状态。"
        ),
    )
    normalized_items: list[NormalizedRetrievalItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。TEL 最终选定 family 返回的标准化候选材料。当前项目中有用："
            "这是 ToolExecutionLayerResult 中最重要的主数据，会被 EvidenceProcessingService 作为 input materials 处理。"
            "每个元素是 NormalizedRetrievalItem，包含 item_id、source_family、source_references、content、content_type、metadata。"
            "source_references 是正式 provenance 列表；metadata 中可能包含各 tool 的扩展信息，例如 docs 的 title/url/section，"
            "web 的 content_fetch_status，paper 的 paper_id/paper_id_type，memory 的 knowledge metadata 等。"
        ),
    )
    acquisition_status: AcquisitionStatus = Field(
        description=(
            "必填字段。本次 TEL request 的最终 acquisition outcome。当前项目中有用："
            "Research Executor、RequestCompletionEvaluationService 相关测试和 EvidenceProcessingService 都依赖这个状态理解 retrieval "
            "是否拿到材料。取值来自共享 AcquisitionStatus 枚举：success、partial_success、no_result、failed。"
            "它表达检索/获取结果质量，不等同于 execution_status；例如 execution_status=completed 时，acquisition_status 仍可能是 no_result。"
        ),
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。family/tool 归一化或过滤过程中丢弃的 item 数量。"
            "当前项目中有用：EvidenceProcessingService 会把它纳入 processing summary 的上游统计；Research Executor "
            "也可以用它解释 partial_success 或材料数量偏少的原因。它不包含 EvidenceProcessing 阶段后续丢弃的 evidence 数量。"
        ),
    )
    source_summary: RetrievalSourceSummary = Field(
        default_factory=RetrievalSourceSummary,
        description=(
            "可选字段，默认空 RetrievalSourceSummary。TEL 最终输出的来源摘要。当前项目中有用："
            "它承接 family/tool 的 provenance，并由 TEL 补充 selected_family 和 normalized_count。"
            "该对象的正式字段包括 selected_family、selected_tool、normalized_count、metadata。"
            "selected_tool 不作为 ToolExecutionLayerResult 顶层字段暴露，但可作为 provenance 保留在这里；"
            "metadata 当前可能包含 tool/adapter-specific 来源摘要，例如 docs 的 searched_sub_source_types、"
            "web 的 provider/domain 覆盖信息、paper 的 provider 信息、memory 的 recall scope 摘要等。"
            "调用方应把它当来源摘要和可观测信息，不应从这里读取候选材料正文。"
        ),
    )
    execution_summary: RetrievalExecutionSummary = Field(
        default_factory=RetrievalExecutionSummary,
        description=(
            "可选字段，默认空 RetrievalExecutionSummary。TEL 最终输出的执行摘要。当前项目中有用："
            "Research Executor 可通过它了解本次 TEL request 的策略版本、是否发生 recovery，以及各阶段状态。"
            "该对象正式字段包括 policy、execution_status、normalized_count、dropped_item_count、retry_count、"
            "fallback_applied、recovery_attempt_count、recovery_exhausted_reason、metrics、observability。"
            "TEL 当前会写入 policy=tool_execution_layer_single_request_v1、family_selection_status、"
            "query_generation_status、evaluation_status、request_completion_status、needs_recovery、recovery_action、"
            "next_step_hint、retry_count、fallback_applied、recovery_attempt_count、recovery_exhausted_reason 等。"
            "其中 metrics 用于数值统计，observability 用于无法稳定建模但有诊断价值的信息；这些扩展 key 不应替代正式字段。"
        ),
    )
    retrieval_trace: RetrievalTrace = Field(
        default_factory=RetrievalTrace,
        description=(
            "可选字段，默认空 RetrievalTrace。TEL 最终输出的轻量检索轨迹。当前项目中有用："
            "Research Executor 和 EvidenceProcessingService 可以用它恢复 retrieval 上下文、生成 evidence metadata、定位失败原因。"
            "该对象正式字段包括 target_problem、selected_family、selected_tool、generated_query、query_focus、"
            "acquisition_status、attempts、returned_refs、errors、context、observability。TEL 当前会写入 target_problem、"
            "selected_family、generated_query、query_focus、acquisition_status、attempts、retry_count、fallback_applied、"
            "recovery_exhausted_reason、family_selection_summary、query_generation_summary、completion_evaluation_summary 等。"
            "errors 中放简短错误摘要；context 放稳定检索上下文；observability 放 tool/family-specific 或调试信息。"
            "它不是完整 tracing framework，也不承载最终答案。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段。TEL 顶层失败摘要。当前项目中有用：当 execution_status=failed 时，Research Executor "
            "可以直接读取该字段得到简短失败原因，例如 family 未选中、query generation 失败、缺少 family service、"
            "memory recall 缺 owner_user_id 或 evaluation failed。该字段应是人类可读的短错误说明，不放 provider raw payload、"
            "大型异常对象或完整 stack trace；更细的结构化错误可查看 retrieval_trace.errors / execution_summary.observability。"
        ),
    )
