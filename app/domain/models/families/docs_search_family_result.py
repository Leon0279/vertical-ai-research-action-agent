"""docs_search family service 的运行时输出模型。"""

from __future__ import annotations

from pydantic import Field

from app.domain.models.families.base_family_execution_result import BaseFamilyExecutionResult


class DocsSearchFamilyResult(BaseFamilyExecutionResult):
    """DocsSearchFamilyService 返回的 family 层标准化结果。

    该模型继承 BaseFamilyExecutionResult，并固定 selected_family 为 docs_search。
    它包装 LlmsTxtDocsSearchToolResult，同时补充 family-level tool selection provenance，
    例如 candidate_tools、selected_tool、preferred_tool_requested 等。当前项目中该结果会被
    ToolExecutionLayerService、RequestCompletionEvaluationService、EvidenceProcessingService
    以及未来新版 Research Executor 链路消费。
    """

    selected_family: str = Field(
        default="docs_search",
        description=(
            "必填字段，默认 docs_search。表示当前 family result 属于 docs_search family。当前项目中该字段有用："
            "DocsSearchFamilyService 固定写入该值；ToolExecutionLayerService 和 RequestCompletionEvaluationService "
            "会校验/使用 selected_family，确保 family execution outcome 与上游 family selection 一致；EvidenceProcessing "
            "也可通过 result / trace / source summary 读取它作为 provenance。"
        ),
    )
