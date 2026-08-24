"""供 Research Executor 与 Tool Execution Layer 传递的压缩检索历史模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import AcquisitionStatus, FamilyName, RetrievalResultUtility


class RecentRetrievalAttempt(BaseModel):
    """已经完成并可供后续 iteration 参考的一条压缩检索尝试。

    该模型不保存 raw provider payload、完整 retrieval trace 或 evidence 正文。它只保留
    Research Executor 调整高层路径、TEL 避免重复低价值 query 所需的最小事实。它不是
    跨 session memory；默认只在一次 Research Stage 执行中累计和传递。
    """

    coverage_target_key: str | None = Field(
        default=None,
        description=(
            "可选字段。此次尝试要推进的 Research Executor coverage target key，例如 objective 或 "
            "sub_question:1。当前项目中有用：ResearchActionDecider 只使用与下一项 evidence "
            "need 相同 target 的历史，避免不同子问题互相影响路径选择。非 Research Executor 调用方可省略。"
        ),
    )
    selected_family: FamilyName = Field(
        description=(
            "必填字段。本次实际执行的 retrieval family。当前项目中有用：Research Executor 用它判断 "
            "memory 或某个 external family 是否已经低价值，TEL 用它过滤当前 selected family 可参考的 query 负例。"
        ),
    )
    selected_tool: str | None = Field(
        default=None,
        description=(
            "可选字段。family 内实际执行的 concrete tool id。当前项目中有用：保留 LLD 要求的 tool-level "
            "history，并支持未来多 tool family 做更精细的规避；当前每个默认 family 通常只有一个 tool。"
        ),
    )
    target_problem: str = Field(
        min_length=1,
        description=(
            "必填字段。当时发送给 TEL 的聚焦 retrieval 问题。当前项目中有用：TEL 只把同一问题上下文中的 "
            "低价值 query 作为负例，避免把其它研究目标的失败经验误用于当前请求。"
        ),
    )
    generated_query: str | None = Field(
        default=None,
        description=(
            "可选字段。当时实际执行的 query 原文。当前项目中有用：符合低价值准入规则时，TEL 从该字段派生 "
            "recent_low_value_queries；没有可用 query 时不参与 query 负例生成。"
        ),
    )
    query_fingerprint: str = Field(
        min_length=1,
        description=(
            "必填字段。对 generated query 做空白、大小写归一化后计算出的稳定摘要指纹。当前项目中有用：用于识别同一 "
            "query pattern 是否已经真实执行并低价值；它不包含、也不替代 generated_query 原文。"
        ),
    )
    result_status: AcquisitionStatus = Field(
        description=(
            "必填字段。本次 family/tool acquisition 的最终状态。当前项目中有用：failed 和 no_result 会被视为 "
            "强低价值信号；success 或 partial_success 仍需结合 result_utility 判断是否推进了研究。"
        ),
    )
    result_utility: RetrievalResultUtility = Field(
        description=(
            "必填字段。本次结果对 coverage target 的实际推进价值。当前项目中有用：由 Research Executor 在 "
            "Evidence Processing 与 iteration outcome 后确定，用于避免重复无效路径，不由 provider 或 TEL 自行猜测。"
        ),
    )
    fallback_applied: bool = Field(
        default=False,
        description=(
            "可选字段，默认 False。该 attempt 是否发生在 TEL 已应用 broader-family fallback 后。当前项目中有用："
            "后续诊断可以区分初始路径与 recovery 路径，且不会把二者误当成同一次单一路径。"
        ),
    )
