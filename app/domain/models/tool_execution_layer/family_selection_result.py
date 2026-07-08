"""Family Selection Service 的输出模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.enums import FamilyName

SelectionStatus = Literal["selected", "no_match", "failed"]


class FamilySelectionResult(BaseModel):
    """family-level routing 的标准化输出。

    该模型表示 Tool Execution Layer 中 family selection 子服务的结果。它只输出 selected_family，
    不输出 selected_tool，也不执行任何 tool。当前项目中该模型有用：ToolExecutionLayerService 会读取
    selected_family 来调用 RetrievalQueryGenerationService 和对应 family service；当 selection failed/no_match 时，
    TEL 会提前停止并把错误信息汇总到 ToolExecutionLayerResult。
    """

    candidate_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。经过 action_mode 初始范围、available_families、allowed_source_families、"
            "blocked_source_families 等约束过滤后剩余的候选 family。当前项目中有用：ToolExecutionLayerService 和测试会用它观察 "
            "selection 候选集是否符合约束；selection_trace 也会保留同一信息。元素类型为 FamilyName，JSON 输出仍是字符串数组。"
            "如果 selection_status 为 no_match 或 failed，该列表通常为空。"
        ),
    )
    ranked_candidate_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。candidate_families 按 deterministic selection policy 排序后的结果。当前项目中有用："
            "FamilySelectionService 会把排序第一位作为 selected_family；preferred_source_families、evidence_goal、evidence_shape、"
            "task_framing、evidence_strategy 和 fallback order 都可能影响排序。元素类型为 FamilyName；no_match/failed 时通常为空。"
        ),
    )
    selected_family: FamilyName | None = Field(
        default=None,
        description=(
            "可选字段。最终选中的 retrieval family。当前项目中有用：ToolExecutionLayerService 会把它传给 "
            "RetrievalQueryGenerationService 生成 query，并用它查找对应 family service；RequestCompletionEvaluationService "
            "后续也会要求 evaluation request 中的 selected_family 与 family execution outcome 的 selected_family 一致。"
            "该字段只表示 family，不表示具体 tool；tool selection 仍由 family service 内部负责。selection_status 为 selected 时应有值，"
            "no_match/failed 时为 None。"
        ),
    )
    selection_status: SelectionStatus = Field(
        description=(
            "必填字段。family selection 的结果状态。当前项目中有用：ToolExecutionLayerService 会根据该字段判断是否继续 query generation。"
            "可选值包括 selected、no_match、failed：selected 表示已选出 selected_family；no_match 表示输入有效但约束过滤后没有候选 family；"
            "failed 表示 family selection 输入或流程失败，例如 target_problem 为空。"
        ),
    )
    selection_summary: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。family selection 的稳定摘要信息，供 TEL 汇总和轻量观测使用。当前项目中有用，但它不是主数据模型；"
            "调用方应优先读取 selected_family、candidate_families、ranked_candidate_families、selection_status 等正式字段。"
            "当前 FamilySelectionService 写入的 key 包括：selected_family（选中的 FamilyName 或 None）、candidate_count（候选 family 数量）、"
            "action_mode（本次选择使用的 ActionMode）、policy（当前固定为 deterministic_family_ranking_v1）。"
            "该 dict 不应放 selected_tool、具体 tool request、adapter response 或 provider raw payload。"
        ),
    )
    selection_trace: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。family selection 的详细可观测轨迹，用于解释 scope、filter 和 ranking 如何发生。当前项目中有用："
            "ToolExecutionLayerService 会把它作为 trace/summary 的一部分保留，测试也会检查其中的候选和排序信息。"
            "selected 成功路径当前包含：target_problem、action_mode、initial_scope、available_families、after_available_filter、"
            "allowed_source_families、after_allowed_filter、blocked_source_families、candidate_families、preferred_source_families、"
            "evidence_goal、evidence_shape、task_type、task_framing、evidence_strategy、ranked_candidate_families。"
            "no_match 路径当前包含上述过滤相关字段以及 family_selection_error。failed 路径当前至少包含 target_problem、action_mode、"
            "family_selection_error。该 dict 用于观测和调试，不应作为下游执行 family/tool 的正式输入。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段。selection failed 或 no_match 时的顶层错误/解释摘要。当前项目中有用：ToolExecutionLayerService 会在无法选中 family "
            "时把该信息作为 failed result 的 error_info 或 trace 信息。selected 成功时通常为 None。该字段应保持简短，"
            "不承载完整 stack trace、provider raw payload 或大型 debug 对象；更细的过滤和排序信息应放 selection_trace。"
        ),
    )
