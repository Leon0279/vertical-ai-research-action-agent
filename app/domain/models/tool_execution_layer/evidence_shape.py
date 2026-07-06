"""family-level retrieval intent 使用的 evidence shape 模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DesiredEvidenceKind = Literal[
    "direct_fact",
    "supporting_evidence",
    "disambiguating_evidence",
    "comparison_evidence",
    "status_evidence",
]
FreshnessRequirement = Literal["normal", "fresh_preferred", "fresh_required"]
EvidenceBreadth = Literal["narrow", "normal", "broad"]


class EvidenceShape(BaseModel):
    """描述本次 retrieval 期望获取什么形态的 evidence。

    该模型当前由 family selection、query generation、ToolExecutionLayerService 等链路消费，
    用于把上游 Research Executor 的证据需求投影成可执行的 retrieval 偏好。它不代表
    evidence 已经充分，也不负责最终答案生成。
    """

    desired_evidence_kind: DesiredEvidenceKind = Field(
        default="supporting_evidence",
        description=(
            "可选字段，默认 supporting_evidence。期望获取的 evidence 类型。当前项目中有用："
            "FamilySelectionService 会用它辅助选择 family，例如 status_evidence 更偏 web_search，"
            "comparison_evidence 更偏 paper_search；RetrievalQueryGenerationService 也会把它放入 LLM prompt，"
            "帮助生成更贴合目标的 query。当前可选值包括 direct_fact、supporting_evidence、"
            "disambiguating_evidence、comparison_evidence、status_evidence。"
        ),
    )
    freshness_requirement: FreshnessRequirement = Field(
        default="normal",
        description=(
            "可选字段，默认 normal。描述本次 retrieval 对新鲜度的要求。当前项目中有用："
            "FamilySelectionService 会用 fresh_required / fresh_preferred 影响 web/docs 的优先级；"
            "ToolExecutionLayerService 会把该值派生为 docs_search / web_search family request 的 "
            "freshness_requirement。当前可选值包括 normal、fresh_preferred、fresh_required。"
        ),
    )
    breadth: EvidenceBreadth = Field(
        default="normal",
        description=(
            "可选字段，默认 normal。描述本次 retrieval 应该偏窄查还是宽查。当前项目中有用："
            "FamilySelectionService 会用 narrow/broad 辅助排序；query generation prompt 也会读取它，"
            "让 generated query 更贴近“直接命中”或“覆盖更广”的检索策略。当前可选值包括 narrow、normal、broad。"
        ),
    )
