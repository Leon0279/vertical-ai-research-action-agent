"""Retrieval Query Generation Service 的输出模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.enums import FamilyName

GenerationStatus = Literal["succeeded", "failed"]


class RetrievalQueryGenerationResult(BaseModel):
    """生成 retrieval query 后返回的标准化结果。

    该模型是 Tool Execution Layer 中 query generation 子服务的公开输出边界。当前项目中该模型有用：
    ToolExecutionLayerService 会读取 generated_query 并映射成对应 family request；如果 generation_status='failed'
    或 generated_query 为空，TEL 会提前停止，不调用 family service。

    重要边界：该模型只表达 query generation 本身，不包含 selected_tool，不包含 retrieval_request，
    不包含 max_results / timeout_limit_ms，也不执行 retrieval。它可以携带最小 summary/trace 方便观测，
    但下游正式执行仍由 family service 和 tool service 负责。
    """

    selected_family: FamilyName | None = Field(
        default=None,
        description=(
            "可选字段。该 query 对应的 retrieval family。当前项目中有用：ToolExecutionLayerService 会用它确认 query 与当前 "
            "family selection 语境一致，并在 retry_same_tool 时复用同一个 query_generation_result。成功和失败路径都会尽量保留该字段；"
            "只有调用方构造异常或未来特殊失败路径中才可能为空。该字段类型为 FamilyName，只表示 family，绝不表示 selected_tool。"
        ),
    )
    generated_query: str | None = Field(
        default=None,
        description=(
            "可选字段。LLM 生成的初始 retrieval query。当前项目中有用：ToolExecutionLayerService 会把它作为 query_text "
            "传给对应 family request，例如 DocsSearchFamilyRequest.query_text、PaperSearchFamilyRequest.query_text、"
            "WebSearchFamilyRequest.query_text 或 ResearchKnowledgeRecallFamilyRequest.query_text。generation_status='succeeded' 时应为非空字符串；"
            "generation_status='failed' 时为 None。该字段不是 executable retrieval request，也不包含 tool-specific 参数。"
        ),
    )
    query_focus: str | None = Field(
        default=None,
        description=(
            "可选字段。对 generated_query 检索重点的短标签或短说明。当前项目中有用：ToolExecutionLayerService 会把它写入 "
            "RetrievalTrace.query_focus / attempt trace，EvidenceProcessingService 也可把它作为 provenance metadata 保留。"
            "generation_status='succeeded' 时应为非空字符串；failed 时为 None。该字段只解释 query 关注点，不参与 family/tool selection。"
        ),
    )
    preserved_terms: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。LLM 在生成 query 时保留的高信息密度术语，例如 API 名、配置项、方法名、论文概念、"
            "产品名或 comparison 对象。当前项目中有用：它提供 query generation 的轻量可观测性，帮助后续人工排查 query 是否丢失关键实体；"
            "当前 TEL 不把它作为执行参数传给 family service。service 会过滤空字符串并去重。failed 时通常为空列表。"
        ),
    )
    generation_status: GenerationStatus = Field(
        description=(
            "必填字段。query generation 是否成功。当前项目中有用：ToolExecutionLayerService 会根据该字段决定是否继续调用 family service。"
            "可选值包括 succeeded 和 failed：succeeded 表示 generated_query/query_focus 已通过 JSON parse 与 Pydantic 校验；"
            "failed 表示 target_problem 为空、LLM 调用异常、LLM 输出非 JSON、缺字段、字段为空或结构校验失败。"
        ),
    )
    generation_summary: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。query generation 的稳定摘要信息，供 TEL 汇总和轻量观测使用。当前项目中有用，但它不是主数据；"
            "调用方应优先读取 selected_family、generated_query、query_focus、generation_status 等正式字段。"
            "当前 RetrievalQueryGenerationService 写入的 key 包括：selected_family（FamilyName）、status（succeeded 或 failed）、"
            "policy（当前固定为 llm_retrieval_query_generation_v1）、recent_low_value_query_count（归一化后实际进入 prompt 的低价值 query 数量）。"
            "该 dict 不应放 selected_tool、完整 prompt、LLM 原始输出、provider raw payload 或 executable retrieval request。"
        ),
    )
    generation_trace: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。query generation 的轻量可观测轨迹，用于解释 LLM prompt 的归一化输入和输出解析方式。"
            "当前项目中有用：ToolExecutionLayerService 会把它保留到最终 trace/summary 中，测试也会检查 prompt/input 信息是否被保留。"
            "当前 RetrievalQueryGenerationService 写入的 key 包括：selected_family、target_problem、evidence_goal、evidence_shape、"
            "success_hint、task_framing、recent_low_value_queries、llm_output_format、parser。"
            "其中 evidence_shape 是 EvidenceShape.model_dump() 后的 dict 或 None；llm_output_format 当前为 json；"
            "parser 当前为 json_loads_pydantic_v1。该 dict 用于 observability，不应作为下游 family execution 的正式 request。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段。generation_status='failed' 时的顶层失败摘要。当前项目中有用：ToolExecutionLayerService 会在 query generation "
            "失败时把该信息作为 failed result 的 error_info。成功时通常为 None。当前可能包含 target_problem 为空、LLM 调用异常、"
            "LLM response was not valid JSON、LLM response did not match the query generation schema、generated_query/query_focus 为空等简短原因。"
            "该字段不应承载完整 LLM 原始输出、完整 prompt、provider raw payload 或 stack trace。"
        ),
    )
