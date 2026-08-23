"""Research Executor 内部的 acquisition action 请求模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import FamilyName
from app.domain.models.tool_execution_layer.request_completion_evaluation_request import (
    FallbackPolicy,
)
from app.services.executor.models.research_executor_types import (
    ResearchActionMode,
    ResearchDesiredEvidenceKind,
    ResearchFreshnessRequirement,
    ResearchGapNature,
    ResearchGapScope,
    ResearchGapSeverity,
    ResearchNeedPurpose,
)


@dataclass
class ResearchActionRequest:
    """Research Executor 为单轮 acquisition 构造的强类型内部请求。

    此模型只在 ResearchActionDecider 与 ResearchMaterialAcquirer 之间传递，
    不是 Tool Execution Layer 的 public request，也不会进入 pipeline、API 或数据库。
    """

    action_mode: ResearchActionMode = field(
        metadata={"description": "必填字段。本轮已选定的内部推进模式。"},
    )
    target_problem: str = field(
        metadata={"description": "必填字段。本轮 acquisition 要解决的聚焦研究问题。"},
    )
    target_scope: str | None = field(
        default=None,
        metadata={"description": "可选字段。本轮优先补充证据的具体对象或问题范围。"},
    )
    gap_scope: ResearchGapScope | None = field(
        default=None,
        metadata={"description": "可选字段。触发本轮 acquisition 的 gap 所在研究层级。"},
    )
    gap_nature: ResearchGapNature | None = field(
        default=None,
        metadata={"description": "可选字段。触发本轮 acquisition 的缺口性质。"},
    )
    gap_severity: ResearchGapSeverity | None = field(
        default=None,
        metadata={"description": "可选字段。触发本轮 acquisition 的缺口严重程度。"},
    )
    gap_summary: str | None = field(
        default=None,
        metadata={"description": "可选字段。当前优先 gap 的简短说明。"},
    )
    evidence_goal: ResearchNeedPurpose | None = field(
        default=None,
        metadata={"description": "可选字段。本轮获取证据要实现的研究目的。"},
    )
    desired_evidence_kind: ResearchDesiredEvidenceKind | None = field(
        default=None,
        metadata={"description": "可选字段。本轮期望证据的 Research Executor 语义类型。"},
    )
    freshness_requirement: ResearchFreshnessRequirement | None = field(
        default=None,
        metadata={"description": "可选字段。本轮证据的新鲜度要求。"},
    )
    allowed_source_families: list[FamilyName] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。本轮允许参与 retrieval 的 family。"},
    )
    preferred_source_families: list[FamilyName] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。本轮优先选择的 retrieval family。"},
    )
    blocked_source_families: list[FamilyName] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。本轮禁止选择的 retrieval family。"},
    )
    max_results: int = field(
        default=5,
        metadata={"description": "可选字段，默认 5。本轮 retrieval 的最大候选结果数量。"},
    )
    scope_restrictions: list[str] = field(
        default_factory=list,
        metadata={"description": "可选字段，默认空列表。需要随本轮 acquisition 传递的范围限制。"},
    )
    success_hint: str | None = field(
        default=None,
        metadata={"description": "可选字段。帮助 TEL query generation 判断有效材料形态的提示。"},
    )
    fallback_policy: FallbackPolicy = field(
        default="fallback_within_same_family",
        metadata={"description": "可选字段。本轮 TEL request 应使用的 recovery fallback 策略。"},
    )
    preferred_tool: str | None = field(
        default=None,
        metadata={"description": "可选字段。可透传给 selected family 的 concrete tool 偏好。"},
    )
