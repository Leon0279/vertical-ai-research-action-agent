"""paper_search family service 的标准化输出模型。"""

from __future__ import annotations

from pydantic import Field

from app.domain.enums import FamilyName
from app.domain.models.families.base_family_execution_result import BaseFamilyExecutionResult


class PaperSearchFamilyResult(BaseFamilyExecutionResult):
    """`PaperSearchFamilyService.run(...)` 返回的 family 层标准化输出。

    该模型包装底层 paper tool 的执行结果，并补充 family-level tool selection provenance。
    当前项目中它会被 ToolExecutionLayerService 消费，再交给 RequestCompletionEvaluationService 判断
    当前 request 是否完成、是否需要 retry/fallback；最终 normalized_items 会继续流向 EvidenceProcessingService。

    继承自 `BaseFamilyExecutionResult` 的公共字段已经有完整中文注释：`normalized_items`、`acquisition_status`、
    `dropped_item_count`、`source_summary`、`execution_summary`、`retrieval_trace`、`error_info`、
    `candidate_tools`、`selected_tool` 等字段在 paper_search family 中仍保持相同语义。特别地：
    `source_summary.metadata` 可保留 paper/tool/provider 级来源摘要；`execution_summary.metrics` 当前会包含
    `candidate_tool_count` 以及底层 tool 写入的 `search_result_count`、`selected_for_fetch_count`、
    `fetch_success_count`、`fetch_empty_count`、`fetch_failed_count`；`retrieval_trace.observability`
    当前可能包含 `attempted_paper_ids`、`selected_paper_ids`、`fetched_paper_ids`、`failed_fetches`。
    """

    selected_family: FamilyName = Field(
        default=FamilyName.PAPER_SEARCH,
        description=(
            "必填字段，默认 `paper_search`。表示该 result 属于 paper_search retrieval family。"
            "当前项目中有用：ToolExecutionLayerService 和 RequestCompletionEvaluationService 会用它确认 family execution outcome "
            "与上游选中的 selected_family 一致；EvidenceProcessingService 也可通过该字段或 source_summary/retrieval_trace "
            "读取 provenance。该字段由 PaperSearchFamilyResult 子类固定默认值，不应由底层 tool 或 adapter 改写为其它 family。"
        ),
    )
