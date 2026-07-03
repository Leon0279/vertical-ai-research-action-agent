"""research_knowledge_memory tool 的运行时输出模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models.retrieval import (
    NormalizedRetrievalItem,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)

AcquisitionStatus = Literal["success", "partial_success", "no_result", "failed"]


class ResearchKnowledgeMemoryToolResult(BaseModel):
    """research_knowledge_memory tool 的标准化执行结果。

    当前项目中该模型会被 ResearchKnowledgeRecallFamilyService 包装成 family result，
    再继续进入 ToolExecutionLayerService、RequestCompletionEvaluationService、
    EvidenceProcessingService 和未来新版 Research Executor 链路。它只描述 memory recall tool
    本次执行结果，不表示最终答案，也不负责 evidence synthesis 或 memory write-back。
    """

    normalized_items: list[NormalizedRetrievalItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。research knowledge recall 归一化后的候选材料主数据。当前项目中该字段有用："
            "ResearchKnowledgeRecallFamilyService 会原样带入 family result，ToolExecutionLayerService 会将最终 "
            "normalized_items 暴露给 EvidenceProcessingService；EvidenceProcessingService 会读取每个 "
            "NormalizedRetrievalItem 的 content、source_family、source_references 和 metadata。"
            "memory tool 当前会把每个 recalled ResearchKnowledgeUnitRecord 转成一个 NormalizedRetrievalItem："
            "content 通常是 knowledge summary，content_type 通常是 knowledge_summary，source_references "
            "来自 knowledge unit 的 distill 前原始 source_refs，可能包含多个 SourceReference。"
            "当 acquisition_status 为 no_result 或 failed 时通常为空。"
        ),
    )
    acquisition_status: AcquisitionStatus = Field(
        description=(
            "必填字段。tool 本次获取 reusable research knowledge 的整体状态。当前项目中该字段有用："
            "family service、ToolExecutionLayerService 和 RequestCompletionEvaluationService 都依赖它判断当前 retrieval "
            "是否成功、是否部分成功、是否无结果或失败。取值含义：success 表示成功召回并归一化出可用材料；"
            "partial_success 表示召回结果中至少有一部分被丢弃但仍有可用材料；no_result 表示没有可用材料；"
            "failed 表示 request 校验、embedding 生成或 memory store recall 失败。"
        ),
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。tool 归一化 recall results 时丢弃的 item 数量。"
            "当前项目中该字段有用：当某个 ResearchKnowledgeRecallResult 无法转换为 NormalizedRetrievalItem "
            "时会计入这里；family / TEL 会保留该统计，EvidenceProcessingService 的 summary 会记录 "
            "upstream_dropped_item_count；它也用于解释 partial_success 的降级来源。"
        ),
    )
    source_summary: RetrievalSourceSummary = Field(
        default_factory=RetrievalSourceSummary,
        description=(
            "可选字段，默认空 RetrievalSourceSummary。来源与 provenance 的摘要。当前项目中该字段有用："
            "research knowledge memory tool 会设置 selected_family=research_knowledge_recall、"
            "selected_tool=research_knowledge_memory_v1、normalized_count。该字段当前通常不需要额外 metadata；"
            "family / TEL / EvidenceProcessing 可读取其中的 selected_tool 和 selected_family 作为 provenance。"
            "如果未来 memory recall 增加 store/provider 级摘要，应优先放入 source_summary.metadata，"
            "而不是新增裸 dict 字段。"
        ),
    )
    execution_summary: RetrievalExecutionSummary = Field(
        default_factory=RetrievalExecutionSummary,
        description=(
            "可选字段，默认空 RetrievalExecutionSummary。执行统计和恢复相关可观测信息。当前项目中该字段有用："
            "research knowledge memory tool 会设置 normalized_count、dropped_item_count；metrics 当前包含 "
            "recall_result_count，表示 memory store 返回的 ResearchKnowledgeRecallResult 数量；observability "
            "当前包含 used_precomputed_embedding，表示本次是否复用了上游传入的 query_embedding。"
            "family 和 TEL 可能在此基础上补充 candidate_tool_count、retry_count、fallback_applied、"
            "recovery_attempt_count 等信息。该字段用于调试、评估 request completion 和解释降级，不承载原始数据库行或大型 payload。"
        ),
    )
    retrieval_trace: RetrievalTrace = Field(
        default_factory=RetrievalTrace,
        description=(
            "可选字段，默认空 RetrievalTrace。轻量 memory recall 轨迹。当前项目中该字段有用："
            "research knowledge memory tool 会写入 returned_refs，当前每个 ref 来自 normalized item 的 primary "
            "SourceReference：优先 source_url，其次 source_id，最后 item_id；context 当前包含 query_text、"
            "used_query_embedding、project_scope_id、allowed_visibility_scopes、knowledge_types、topic_tags、"
            "source_types。失败路径会在 errors 中写入 recall_error。family / TEL 可能继续补充 selected_family、"
            "selected_tool、generated_query、query_focus、attempts 等字段。该字段用于后续 EvidenceProcessing 的语境读取和运行时诊断。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段。tool 顶层失败摘要。当前项目中该字段有用：当 acquisition_status=failed 时，"
            "ResearchKnowledgeMemoryTool 会把 request 校验错误、embedding client 异常或 memory store recall 异常"
            "转成简短字符串放在这里；family / TEL 会保留该错误，用于失败结果和 recovery evaluation。"
            "该字段不应放数据库原始行、完整 stack trace、embedding 向量或大型 debug payload。"
        ),
    )
