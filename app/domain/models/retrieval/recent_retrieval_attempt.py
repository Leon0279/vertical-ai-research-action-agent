"""供 Research Executor 与 Tool Execution Layer 传递的压缩检索历史模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import AcquisitionStatus, FamilyName, RetrievalResultUtility


class RecentRetrievalAttempt(BaseModel):
    """已经完成并可供后续 iteration 参考的一条压缩检索尝试。

    该模型不保存 raw provider payload、完整 retrieval trace 或 evidence 正文。它只保留
    Assessment LLM 理解此前尝试、TEL 构造可选 query 提示所需的最小事实。它不是
    跨 session memory，也不会形成 family blacklist；默认只在一次 Research Stage 执行中累计和传递。
    """

    coverage_target_key: str | None = Field(
        default=None,
        description=(
            "可选字段。此次尝试要推进的 Research Executor coverage target key，例如 objective 或 "
            "sub_question:1。当前项目中有用：帮助 Assessment LLM 和 TEL 区分不同研究对象的历史，"
            "避免把一个子问题的尝试误认为另一个子问题的结果。非 Research Executor 调用方可省略。"
        ),
    )
    selected_family: FamilyName = Field(
        description=(
            "必填字段。本次实际执行的 retrieval family。当前项目中有用：让 Assessment LLM 理解此前使用的"
            "资料渠道，并让 TEL 在需要自行生成 query 时筛选同 family 的历史提示；它不直接禁止再次选择该 family。"
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
            "必填字段。当时发送给 TEL 的聚焦 retrieval 问题。当前项目中有用：帮助 LLM 与 TEL 判断历史"
            "是否属于同一问题上下文，避免把其它研究目标的经验误用于当前请求。"
        ),
    )
    generated_query: str | None = Field(
        default=None,
        description=(
            "可选字段。当时实际执行的 query 原文。当前项目中有用：Assessment LLM 可参考它调整后续表达；"
            "当 TEL 需要自行生成 query 时，也可从该字段派生软性的 query 负例。"
        ),
    )
    query_fingerprint: str = Field(
        min_length=1,
        description=(
            "必填字段。对 generated query 做空白、大小写归一化后计算出的稳定摘要指纹。当前项目中有用：用于日志"
            "关联和识别重复 query pattern；它不包含、也不替代 generated_query 原文。"
        ),
    )
    result_status: AcquisitionStatus = Field(
        description=(
            "必填字段。本次 family/tool acquisition 的最终状态。当前项目中有用：让 Assessment LLM 区分"
            "成功、失败和无结果尝试；success 或 partial_success 仍需结合 result_utility 理解实际推进程度。"
        ),
    )
    result_utility: RetrievalResultUtility = Field(
        description=(
            "必填字段。本次结果对 coverage target 的实际推进价值。当前项目中有用：由 Research Executor 在 "
            "Evidence Processing 与 iteration outcome 后确定，作为后续 LLM 判断的参考，不由 provider 或 TEL 自行猜测。"
        ),
    )
    fallback_applied: bool = Field(
        default=False,
        description=(
            "可选字段，默认 False。该 attempt 是否发生在 TEL 已应用 broader-family fallback 后。当前项目中有用："
            "后续诊断可以区分初始路径与 recovery 路径，且不会把二者误当成同一次单一路径。"
        ),
    )
