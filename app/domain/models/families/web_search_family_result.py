"""web_search family service 的标准化输出模型。"""

from __future__ import annotations

from pydantic import Field

from app.domain.models.families.base_family_execution_result import BaseFamilyExecutionResult


class WebSearchFamilyResult(BaseFamilyExecutionResult):
    """`WebSearchFamilyService.run(...)` 返回的 family-level 执行结果。

    该模型继承 `BaseFamilyExecutionResult`，公共字段如 `normalized_items`、`acquisition_status`、
    `dropped_item_count`、`source_summary`、`execution_summary`、`retrieval_trace`、`error_info`、
    `candidate_tools`、`selected_tool` 已在基类中有完整中文注释。

    当前项目中该 result 有用：ToolExecutionLayerService 会消费它作为一次 family execution outcome；
    RequestCompletionEvaluationService 会读取 `acquisition_status`、`candidate_tools`、`selected_tool`
    判断是否 complete/retry/fallback；EvidenceProcessingService 最终会消费其中的 normalized items。

    `WebSearchFamilyService` 当前会在包装 tool result 时补充：
    `source_summary.selected_family='web_search'`、`source_summary.selected_tool`、
    `execution_summary.metrics['candidate_tool_count']`、
    `execution_summary.observability['preferred_tool_requested']`，
    以及 `retrieval_trace.selected_family`、`retrieval_trace.selected_tool`、
    `retrieval_trace.context['candidate_tools']`、`retrieval_trace.context['preferred_tool']`。
    失败路径还会在 `retrieval_trace.errors['family_error']` 中放简短 family 错误。
    """

    selected_family: str = Field(
        default="web_search",
        description=(
            "必填字段，有默认值 `web_search`；表示本 result 所属的 retrieval family。"
            "当前项目中有用：ToolExecutionLayerService 和 RequestCompletionEvaluationService 会用它校验 "
            "family execution outcome 是否与当前 selected family 一致，并作为 provenance 继续传给后续 evidence "
            "processing / tracing。该字段应恒为 `web_search`，不表示具体 tool；具体 tool 选择结果应看 "
            "`selected_tool` 或 `source_summary.selected_tool`。"
        ),
    )
