"""research_knowledge_recall family service 的运行时输出模型。"""

from __future__ import annotations

from pydantic import Field

from app.domain.enums import FamilyName
from app.domain.models.families.base_family_execution_result import BaseFamilyExecutionResult


class ResearchKnowledgeRecallFamilyResult(BaseFamilyExecutionResult):
    """ResearchKnowledgeRecallFamilyService 返回的 family 层标准化结果。

    该模型继承 BaseFamilyExecutionResult，并固定 selected_family 为 research_knowledge_recall。
    它包装 ResearchKnowledgeMemoryToolResult，同时补充 family-level tool selection provenance，
    例如 candidate_tools、selected_tool、preferred_tool_requested 等。当前项目中该结果会被
    ToolExecutionLayerService、RequestCompletionEvaluationService、EvidenceProcessingService
    以及未来新版 Research Executor 链路消费。

    继承字段说明：
    - normalized_items：来自 ResearchKnowledgeMemoryToolResult.normalized_items；当前每个 item 通常对应一个
      ResearchKnowledgeUnitRecord 的 reusable knowledge summary，source_references 可能包含多个 distill 前原始 SourceReference。
    - acquisition_status：来自 tool result 或 family failed path；TEL/evaluator 会用它判断 complete/recovery。
    - dropped_item_count：来自 tool result；表示 recall result 到 normalized item 转换时被丢弃的数量。
    - source_summary：typed RetrievalSourceSummary；当前会包含 selected_family、selected_tool、normalized_count。
    - execution_summary：typed RetrievalExecutionSummary；当前会保留 recall_result_count、used_precomputed_embedding，
      family 层还会补 candidate_tool_count 和 preferred_tool_requested。
    - retrieval_trace：typed RetrievalTrace；当前会保留 query_text、memory filters、returned_refs、selected_family、
      selected_tool、candidate_tools、preferred_tool，失败时 errors 可包含 family_error。
    - error_info：family 或 tool 顶层失败摘要，不承载原始数据库行、完整 stack trace 或大型 debug payload。
    """

    selected_family: FamilyName = Field(
        default=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
        description=(
            "必填字段，默认 research_knowledge_recall。表示当前 family result 属于 research_knowledge_recall family。"
            "当前项目中该字段有用：ResearchKnowledgeRecallFamilyService 固定写入该值；"
            "ToolExecutionLayerService 和 RequestCompletionEvaluationService 会校验/使用 selected_family，"
            "确保 family execution outcome 与上游 family selection 一致；EvidenceProcessing 也可通过 result / trace / "
            "source summary 读取它作为 provenance。"
        ),
    )
