"""Research Executor 内部的确定性 action decision 协作者。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.domain.enums import FamilyName
from app.services.executor.models.research_action_decider_input import (
    ResearchActionDeciderInput,
)
from app.services.executor.models.research_action_decider_output import (
    ResearchActionDeciderOutput,
)
from app.services.executor.models.research_action_request import ResearchActionRequest
from app.services.executor.enums import (
    ResearchActionDecisionReason,
    ResearchActionMode,
    ResearchDesiredEvidenceKind,
    ResearchFindingMaturity,
    ResearchFreshnessRequirement,
    ResearchGapNature,
    ResearchGapSeverity,
    ResearchSupportStrength,
)
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)
from app.services.executor.research_retrieval_history_tracker import (
    ResearchRetrievalHistoryTracker,
)

_EXTERNAL_FAMILIES = {
    FamilyName.DOCS_SEARCH,
    FamilyName.PAPER_SEARCH,
    FamilyName.WEB_SEARCH,
}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ResearchActionDecisionDiagnostics:
    """保存本轮 action decision 在历史过滤前后的最小诊断状态。"""

    available_families: list[FamilyName]
    low_value_families: list[FamilyName]
    memory_eligible_before_history: bool
    external_eligible_before_history: bool
    external_families_before_history: list[FamilyName]
    external_families_after_history: list[FamilyName]


class ResearchActionDecider(ResearchExecutorCollaboratorSupport):
    """根据 assessment 与 runtime 约束选择本轮是否进入 acquisition。"""

    def __init__(
        self,
        *,
        retrieval_history_tracker: ResearchRetrievalHistoryTracker,
    ) -> None:
        self._retrieval_history_tracker = retrieval_history_tracker

    async def decide(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> ResearchActionDeciderOutput:
        """根据只读输入快照选择 action，并返回完整的强类型决策。

        Args:
            decider_input: ``ResearchActionDeciderInput`` 类型。包含当前评估、
                evidence need、检索历史、可用 family 和运行预算快照。

        Returns:
            ``ResearchActionDeciderOutput`` 类型。包含候选模式、最终模式、
            规则原因、路径耗尽状态和可选 acquisition request。
        """

        top_gap = decider_input.top_gap
        next_evidence_need = decider_input.next_evidence_need
        diagnostics = self._decision_diagnostics(decider_input)
        acquisition_paths_exhausted = self._acquisition_paths_exhausted(
            decider_input
        )
        candidate_action_modes = self._candidate_action_modes(decider_input)
        action_mode, action_decision_reason = self._select_action_mode(
            candidate_action_modes,
            decider_input,
            acquisition_paths_exhausted,
            diagnostics,
        )
        output = ResearchActionDeciderOutput(
            candidate_action_modes=candidate_action_modes,
            action_mode=action_mode,
            action_decision_reason=action_decision_reason,
            action_rationale=self._action_rationale(action_decision_reason),
            acquisition_paths_exhausted=acquisition_paths_exhausted,
            action_request=self._build_action_request(
                action_mode,
                decider_input,
                diagnostics,
            ),
        )
        action_request = output.action_request
        logger.info(
            "Research action selected.",
            extra={
                "event": "research_action_selected",
                "iteration_index": decider_input.iteration_index,
                "remaining_iteration_budget": (
                    decider_input.remaining_iteration_budget
                ),
                "candidate_action_modes": output.candidate_action_modes,
                "action_mode": output.action_mode,
                "action_decision_reason": output.action_decision_reason,
                "action_rationale": output.action_rationale,
                "acquisition_paths_exhausted": (
                    output.acquisition_paths_exhausted
                ),
                "top_gap_nature": top_gap.gap_nature,
                "top_gap_severity": top_gap.gap_severity,
                "evidence_need_purpose": next_evidence_need.need_purpose,
                "desired_evidence_kind": (
                    next_evidence_need.desired_evidence_kind
                ),
                "freshness_requirement": (
                    next_evidence_need.freshness_requirement
                ),
                "coverage_target_key": next_evidence_need.coverage_target_key,
                "allowed_source_families": (
                    list(action_request.allowed_source_families)
                    if action_request is not None
                    else []
                ),
                "preferred_source_families": (
                    list(action_request.preferred_source_families)
                    if action_request is not None
                    else []
                ),
                "blocked_source_families": (
                    list(action_request.blocked_source_families)
                    if action_request is not None
                    else []
                ),
                "fallback_policy": (
                    action_request.fallback_policy
                    if action_request is not None
                    else None
                ),
                "available_families": diagnostics.available_families,
                "low_value_families": diagnostics.low_value_families,
                "memory_eligible_before_history": (
                    diagnostics.memory_eligible_before_history
                ),
                "external_eligible_before_history": (
                    diagnostics.external_eligible_before_history
                ),
                "external_families_before_history": (
                    diagnostics.external_families_before_history
                ),
                "external_families_after_history": (
                    diagnostics.external_families_after_history
                ),
            },
        )
        return output

    def _decision_diagnostics(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> _ResearchActionDecisionDiagnostics:
        """计算不影响业务选择的路径资格与历史过滤诊断数据。"""

        available_families = self._ordered_unique_families(
            decider_input.available_families,
        )
        low_value_family_set = self._low_value_families(decider_input)
        low_value_families = [
            family
            for family in available_families
            if family in low_value_family_set
        ]
        low_value_families.extend(
            sorted(
                low_value_family_set - set(low_value_families),
                key=lambda family: family.value,
            )
        )
        return _ResearchActionDecisionDiagnostics(
            available_families=available_families,
            low_value_families=low_value_families,
            memory_eligible_before_history=(
                self._memory_acquisition_eligible_without_history(
                    decider_input,
                )
            ),
            external_eligible_before_history=(
                self._external_acquisition_eligible_without_history(
                    decider_input,
                )
            ),
            external_families_before_history=self._ordered_unique_families(
                self._external_source_families(decider_input),
            ),
            external_families_after_history=self._ordered_unique_families(
                self._external_source_families_for_current_target(
                    decider_input,
                )
            ),
        )

    def _candidate_action_modes(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> list[ResearchActionMode]:
        """应用确定性 gate，生成本轮可行的 action mode。"""

        if self._must_refine_from_existing_state(decider_input):
            return [ResearchActionMode.REFINE_FROM_EXISTING_STATE]

        candidate_modes: list[ResearchActionMode] = [
            ResearchActionMode.REFINE_FROM_EXISTING_STATE
        ]
        if self._memory_acquisition_available(decider_input):
            candidate_modes.append(ResearchActionMode.MEMORY_BACKED_ACQUISITION)
        if self._external_acquisition_available(decider_input):
            candidate_modes.append(ResearchActionMode.EXTERNAL_ACQUISITION)
        return candidate_modes

    def _must_refine_from_existing_state(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> bool:
        """判断 acquisition 是否明确无必要或不可用。"""

        if decider_input.remaining_iteration_budget <= 0:
            return True
        if self._has_no_actionable_evidence_need(
            decider_input.top_gap,
            decider_input.next_evidence_need,
        ):
            return True
        if (
            decider_input.current_assessment.finding_maturity
            == ResearchFindingMaturity.STABLE
            and decider_input.current_assessment.support_strength
            == ResearchSupportStrength.STRONG_ENOUGH
        ):
            return True
        if not decider_input.available_families:
            return True
        return (
            self._is_latency_constrained(decider_input)
            and decider_input.top_gap.gap_severity != ResearchGapSeverity.BLOCKING
        )

    def _memory_acquisition_available(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> bool:
        """判断 memory-backed acquisition 是否是有效候选。"""

        return (
            self._memory_acquisition_eligible_without_history(decider_input)
            and FamilyName.RESEARCH_KNOWLEDGE_RECALL
            not in self._low_value_families(decider_input)
        )

    def _external_acquisition_available(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> bool:
        """判断 external acquisition 是否是有效候选。"""

        external_families = self._external_source_families_for_current_target(
            decider_input,
        )
        return bool(external_families) and (
            self._external_acquisition_eligible_without_history(decider_input)
            # 同一 target 的 memory 已被验证低价值时，只要外部能力仍可用，就切换
            # 路径而不是继续无意义地只做 state refinement。
            or FamilyName.RESEARCH_KNOWLEDGE_RECALL
            in self._low_value_families(decider_input)
        )

    def _select_action_mode(
        self,
        candidate_action_modes: list[ResearchActionMode],
        decider_input: ResearchActionDeciderInput,
        acquisition_paths_exhausted: bool,
        diagnostics: _ResearchActionDecisionDiagnostics,
    ) -> tuple[ResearchActionMode, ResearchActionDecisionReason]:
        """从候选中选择 action mode，并返回与该分支一致的稳定原因码。"""

        if len(candidate_action_modes) == 1:
            return candidate_action_modes[0], self._refine_decision_reason(
                decider_input,
                acquisition_paths_exhausted,
            )
        if (
            ResearchActionMode.EXTERNAL_ACQUISITION in candidate_action_modes
            and (
                decider_input.next_evidence_need.freshness_requirement
                == ResearchFreshnessRequirement.FRESH_REQUIRED
                or decider_input.top_gap.gap_nature == ResearchGapNature.STALE
            )
        ):
            return (
                ResearchActionMode.EXTERNAL_ACQUISITION,
                ResearchActionDecisionReason.FRESH_OR_STALE_REQUIRES_EXTERNAL,
            )
        if ResearchActionMode.MEMORY_BACKED_ACQUISITION in candidate_action_modes:
            if ResearchActionMode.EXTERNAL_ACQUISITION in candidate_action_modes:
                return (
                    ResearchActionMode.MEMORY_BACKED_ACQUISITION,
                    ResearchActionDecisionReason.MEMORY_PREFERRED_BY_DEFAULT,
                )
            return (
                ResearchActionMode.MEMORY_BACKED_ACQUISITION,
                ResearchActionDecisionReason.MEMORY_ONLY_CANDIDATE,
            )
        if ResearchActionMode.EXTERNAL_ACQUISITION in candidate_action_modes:
            if (
                diagnostics.memory_eligible_before_history
                and FamilyName.RESEARCH_KNOWLEDGE_RECALL
                in diagnostics.low_value_families
            ):
                return (
                    ResearchActionMode.EXTERNAL_ACQUISITION,
                    ResearchActionDecisionReason.MEMORY_BLOCKED_BY_HISTORY,
                )
            return (
                ResearchActionMode.EXTERNAL_ACQUISITION,
                ResearchActionDecisionReason.EXTERNAL_ONLY_CANDIDATE,
            )
        return (
            ResearchActionMode.REFINE_FROM_EXISTING_STATE,
            ResearchActionDecisionReason.NO_ELIGIBLE_ACQUISITION_PATH,
        )

    def _refine_decision_reason(
        self,
        decider_input: ResearchActionDeciderInput,
        acquisition_paths_exhausted: bool,
    ) -> ResearchActionDecisionReason:
        """按照 refine gate 的实际优先顺序返回唯一原因码。"""

        if acquisition_paths_exhausted:
            return ResearchActionDecisionReason.ACQUISITION_PATHS_EXHAUSTED
        if decider_input.remaining_iteration_budget <= 0:
            return ResearchActionDecisionReason.ITERATION_BUDGET_EXHAUSTED
        if self._has_no_actionable_evidence_need(
            decider_input.top_gap,
            decider_input.next_evidence_need,
        ):
            return ResearchActionDecisionReason.NO_ACTIONABLE_GAP
        if (
            decider_input.current_assessment.finding_maturity
            == ResearchFindingMaturity.STABLE
            and decider_input.current_assessment.support_strength
            == ResearchSupportStrength.STRONG_ENOUGH
        ):
            return ResearchActionDecisionReason.STABLE_WITH_STRONG_SUPPORT
        if not decider_input.available_families:
            return ResearchActionDecisionReason.NO_AVAILABLE_FAMILY
        if (
            self._is_latency_constrained(decider_input)
            and decider_input.top_gap.gap_severity != ResearchGapSeverity.BLOCKING
        ):
            return ResearchActionDecisionReason.LATENCY_CONSTRAINED
        return ResearchActionDecisionReason.NO_ELIGIBLE_ACQUISITION_PATH

    def _build_action_request(
        self,
        action_mode: ResearchActionMode,
        decider_input: ResearchActionDeciderInput,
        diagnostics: _ResearchActionDecisionDiagnostics,
    ) -> ResearchActionRequest | None:
        """构造 acquisition path 所需的强类型 action request。"""

        if action_mode == ResearchActionMode.REFINE_FROM_EXISTING_STATE:
            return None
        allowed_source_families = self._allowed_source_families_for_action(
            action_mode,
            decider_input,
        )
        blocked_source_families = self._blocked_source_families_for_action(
            action_mode,
            diagnostics,
        )
        return ResearchActionRequest(
            action_mode=action_mode,
            target_scope=self._action_target_scope(decider_input),
            target_problem=self._action_target_problem(decider_input),
            gap_scope=decider_input.top_gap.gap_scope,
            gap_nature=decider_input.top_gap.gap_nature,
            gap_severity=decider_input.top_gap.gap_severity,
            gap_summary=decider_input.top_gap.gap_summary,
            evidence_goal=decider_input.next_evidence_need.need_purpose,
            desired_evidence_kind=(
                decider_input.next_evidence_need.desired_evidence_kind
            ),
            freshness_requirement=(
                decider_input.next_evidence_need.freshness_requirement
            ),
            allowed_source_families=allowed_source_families,
            preferred_source_families=self._preferred_source_families_for_action(
                action_mode,
                allowed_source_families,
            ),
            blocked_source_families=blocked_source_families,
            scope_restrictions=list(decider_input.scope_restrictions),
            success_hint=(
                decider_input.next_evidence_need.need_summary
                or decider_input.top_gap.gap_actionability
            ),
            fallback_policy=(
                "fallback_within_same_family"
                if action_mode == ResearchActionMode.MEMORY_BACKED_ACQUISITION
                else "fallback_to_broader_search"
            ),
        )

    @staticmethod
    def _preferred_source_families_for_action(
        action_mode: ResearchActionMode,
        allowed_source_families: list[FamilyName],
    ) -> list[FamilyName]:
        """Preserve an explicit memory choice without overriding external ranking."""

        if action_mode == ResearchActionMode.MEMORY_BACKED_ACQUISITION:
            return list(allowed_source_families)
        return []

    def _allowed_source_families_for_action(
        self,
        action_mode: ResearchActionMode,
        decider_input: ResearchActionDeciderInput,
    ) -> list[FamilyName]:
        """解析本轮 action request 的 retrieval family 约束。"""

        if action_mode == ResearchActionMode.MEMORY_BACKED_ACQUISITION:
            return [FamilyName.RESEARCH_KNOWLEDGE_RECALL]
        if action_mode == ResearchActionMode.EXTERNAL_ACQUISITION:
            return self._external_source_families_for_current_target(
                decider_input,
            )
        return []

    def _blocked_source_families_for_action(
        self,
        action_mode: ResearchActionMode,
        diagnostics: _ResearchActionDecisionDiagnostics,
    ) -> list[FamilyName]:
        """仅把当前 target 已验证低价值的 external family 传给 TEL。"""

        if action_mode != ResearchActionMode.EXTERNAL_ACQUISITION:
            return []
        return [
            family
            for family in diagnostics.low_value_families
            if family in _EXTERNAL_FAMILIES
        ]

    def _action_target_scope(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> str | None:
        """返回 action intent 可用的最具体目标范围。"""

        return (
            decider_input.next_evidence_need.need_target
            or decider_input.top_gap.gap_target
            or decider_input.next_evidence_need.need_scope
            or decider_input.top_gap.gap_scope
        )

    def _action_target_problem(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> str:
        """返回后续 acquisition 要解决的具体问题。"""

        return (
            decider_input.next_evidence_need.need_summary
            or decider_input.top_gap.gap_summary
            or decider_input.user_goal
            or decider_input.original_query
        )

    def _action_rationale(
        self,
        decision_reason: ResearchActionDecisionReason,
    ) -> str:
        """根据稳定原因码构造对应的人类可读说明。"""

        rationale_by_reason: dict[ResearchActionDecisionReason, str] = {
            ResearchActionDecisionReason.ITERATION_BUDGET_EXHAUSTED: (
                "当前 iteration budget 已耗尽，因此不再发起 acquisition。"
            ),
            ResearchActionDecisionReason.NO_ACTIONABLE_GAP: (
                "当前 top_gap / next_evidence_need 表示没有可推进的 actionable gap，因此不发起 acquisition。"
            ),
            ResearchActionDecisionReason.STABLE_WITH_STRONG_SUPPORT: (
                "当前 finding 已稳定且支撑强度足够，因此更适合 refine existing state。"
            ),
            ResearchActionDecisionReason.NO_AVAILABLE_FAMILY: (
                "当前 runtime 未声明 acquisition capability，因此本轮基于已有 state refine。"
            ),
            ResearchActionDecisionReason.LATENCY_CONSTRAINED: (
                "当前 latency budget 较紧且 gap 不是 blocking，因此避免新增 acquisition。"
            ),
            ResearchActionDecisionReason.ACQUISITION_PATHS_EXHAUSTED: (
                "当前 coverage target 的所有兼容 acquisition 路径都已被近期历史判定为低价值，因此不重复检索并等待降级收束。"
            ),
            ResearchActionDecisionReason.FRESH_OR_STALE_REQUIRES_EXTERNAL: (
                "当前 evidence need 要求 fresh evidence，或 gap 已陈旧，因此优先 external acquisition。"
            ),
            ResearchActionDecisionReason.MEMORY_PREFERRED_BY_DEFAULT: (
                "memory 与 external 路径都可用；当前不要求 fresh evidence，因此按默认优先级选择 memory-backed acquisition。"
            ),
            ResearchActionDecisionReason.MEMORY_ONLY_CANDIDATE: (
                "当前只有 memory 路径满足 evidence need 与 runtime 约束，因此选择 memory-backed acquisition。"
            ),
            ResearchActionDecisionReason.MEMORY_BLOCKED_BY_HISTORY: (
                "memory 路径此前未有效推进当前 coverage target，因此切换到仍可用的 external acquisition。"
            ),
            ResearchActionDecisionReason.EXTERNAL_ONLY_CANDIDATE: (
                "当前只有 external 路径满足 evidence need 与 runtime 约束，因此选择 external acquisition。"
            ),
            ResearchActionDecisionReason.NO_ELIGIBLE_ACQUISITION_PATH: (
                "当前没有满足约束的 acquisition path，因此基于已有 state refine。"
            ),
        }
        return rationale_by_reason[decision_reason]

    def _acquisition_paths_exhausted(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> bool:
        """判断历史是否已耗尽当前 target 的全部规则允许 acquisition 路径。"""

        if self._must_refine_from_existing_state(decider_input):
            return False

        low_value_families = self._low_value_families(decider_input)
        memory_eligible = self._memory_acquisition_eligible_without_history(
            decider_input
        )
        external_families = self._external_source_families(decider_input)
        external_eligible = bool(external_families) and (
            self._external_acquisition_eligible_without_history(
                decider_input,
            )
            or FamilyName.RESEARCH_KNOWLEDGE_RECALL in low_value_families
        )
        if not memory_eligible and not external_eligible:
            return False
        memory_exhausted = (
            not memory_eligible
            or FamilyName.RESEARCH_KNOWLEDGE_RECALL in low_value_families
        )
        external_exhausted = not external_eligible or all(
            family in low_value_families for family in external_families
        )
        return memory_exhausted and external_exhausted

    def _memory_acquisition_eligible_without_history(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> bool:
        """只根据当前 need 与 capability 判断 memory path 的基础适用性。"""

        return (
            self._has_memory_capability(decider_input)
            and decider_input.next_evidence_need.freshness_requirement
            != ResearchFreshnessRequirement.FRESH_REQUIRED
            and decider_input.top_gap.gap_nature not in {ResearchGapNature.STALE, ResearchGapNature.IMBALANCED}
        )

    def _external_acquisition_eligible_without_history(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> bool:
        """只根据当前 need 与 capability 判断 external path 的基础适用性。"""

        return bool(self._external_source_families(decider_input)) and (
            decider_input.top_gap.gap_nature in {ResearchGapNature.MISSING, ResearchGapNature.STALE, ResearchGapNature.IMBALANCED}
            or decider_input.next_evidence_need.freshness_requirement
            == ResearchFreshnessRequirement.FRESH_REQUIRED
            or decider_input.next_evidence_need.desired_evidence_kind
            in {ResearchDesiredEvidenceKind.DIRECT_FACT, ResearchDesiredEvidenceKind.COMPARISON_EVIDENCE, ResearchDesiredEvidenceKind.FRESH_STATUS_EVIDENCE}
        )

    def _external_source_families_for_current_target(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> list[FamilyName]:
        """排除当前 target 已明确低价值的 external family。"""

        low_value_families = self._low_value_families(decider_input)
        return [
            family
            for family in self._external_source_families(decider_input)
            if family not in low_value_families
        ]

    def _low_value_families(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> set[FamilyName]:
        """返回与当前 evidence need 同 coverage target 的已验证低价值 family。"""

        return self._retrieval_history_tracker.low_value_families_for_target(
            decider_input.recent_retrieval_attempts,
            decider_input.next_evidence_need.coverage_target_key,
        )

    def _has_memory_capability(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> bool:
        """判断 runtime family 是否包含 memory acquisition 路径。"""

        return (
            FamilyName.RESEARCH_KNOWLEDGE_RECALL
            in decider_input.available_families
        )

    def _external_source_families(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> list[FamilyName]:
        """返回当前 runtime 中按原顺序可选的 external retrieval family。"""

        return [
            family
            for family in decider_input.available_families
            if family in _EXTERNAL_FAMILIES
        ]

    @staticmethod
    def _ordered_unique_families(
        families: list[FamilyName],
    ) -> list[FamilyName]:
        """按首次出现顺序返回稳定且无重复的 retrieval family 列表。"""

        return list(dict.fromkeys(families))

    def _is_latency_constrained(
        self,
        decider_input: ResearchActionDeciderInput,
    ) -> bool:
        """判断 latency budget 是否应抑制非阻塞 acquisition。"""

        return (
            decider_input.latency_budget_ms is not None
            and decider_input.latency_budget_ms <= 1000
        )
