"""Research Executor 内部的确定性 action decision 协作者。"""

from __future__ import annotations

from typing import Any

from app.domain.enums import FamilyName
from app.domain.models import ResearchStageInput
from app.services.executor.models.research_executor_types import (
    EXTERNAL_ACTION_MODE as _EXTERNAL_ACTION_MODE,
    MEMORY_ACTION_MODE as _MEMORY_ACTION_MODE,
    REFINE_ACTION_MODE as _REFINE_ACTION_MODE,
    ResearchActionMode,
)
from app.services.executor.research_executor_collaborator_support import (
    ResearchExecutorCollaboratorSupport,
)

_MEMORY_CAPABILITY_NAMES = {
    "memory",
    "memory_backed_acquisition",
    "research_knowledge_memory",
    FamilyName.RESEARCH_KNOWLEDGE_RECALL.value,
}
_EXTERNAL_CAPABILITY_FAMILY_MAP = {
    "docs": FamilyName.DOCS_SEARCH.value,
    "docs_search": FamilyName.DOCS_SEARCH.value,
    "llms_txt_docs_search_v1": FamilyName.DOCS_SEARCH.value,
    "paper": FamilyName.PAPER_SEARCH.value,
    "paper_search": FamilyName.PAPER_SEARCH.value,
    "arxiv_paper_search_v1": FamilyName.PAPER_SEARCH.value,
    "web": FamilyName.WEB_SEARCH.value,
    "web_search": FamilyName.WEB_SEARCH.value,
    "tavily_web_search_v1": FamilyName.WEB_SEARCH.value,
}
_EXTERNAL_ALL_CAPABILITY_NAMES = {"external", "external_acquisition"}


class ResearchActionDecider(ResearchExecutorCollaboratorSupport):
    """根据 assessment 与 runtime 约束选择本轮是否进入 acquisition。"""

    async def decide(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> bool:
        """Step 3. Decide whether this iteration should enter acquisition."""

        assessment = self._working_state_dict(working_state, "current_assessment")
        top_gap = self._working_state_dict(working_state, "top_gap")
        next_evidence_need = self._working_state_dict(
            working_state,
            "next_evidence_need",
        )
        candidate_action_modes = self._candidate_action_modes(
            stage_input,
            working_state,
            assessment,
            top_gap,
            next_evidence_need,
        )
        action_mode = self._select_action_mode(
            candidate_action_modes,
            top_gap,
            next_evidence_need,
        )
        action_request = self._build_action_request(
            action_mode,
            stage_input,
            top_gap,
            next_evidence_need,
        )

        working_state["candidate_action_modes"] = candidate_action_modes
        working_state["action_mode"] = action_mode
        working_state["action_rationale"] = self._action_rationale(
            action_mode,
            stage_input,
            assessment,
            top_gap,
            next_evidence_need,
        )
        working_state["action_request"] = action_request

        return action_mode != _REFINE_ACTION_MODE


    def _candidate_action_modes(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
        assessment: dict[str, Any],
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> list[ResearchActionMode]:
        """Apply deterministic gates to form candidate 4.5 action modes."""

        if self._must_refine_from_existing_state(
            stage_input,
            working_state,
            assessment,
            top_gap,
            next_evidence_need,
        ):
            return [_REFINE_ACTION_MODE]

        candidate_modes: list[ResearchActionMode] = [_REFINE_ACTION_MODE]
        if self._memory_acquisition_available(stage_input, top_gap, next_evidence_need):
            candidate_modes.append(_MEMORY_ACTION_MODE)
        if self._external_acquisition_available(stage_input, top_gap, next_evidence_need):
            candidate_modes.append(_EXTERNAL_ACTION_MODE)
        return candidate_modes


    def _must_refine_from_existing_state(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
        assessment: dict[str, Any],
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> bool:
        """Return True when acquisition is clearly unnecessary or unavailable."""

        remaining_iteration_budget = working_state.get("remaining_iteration_budget")
        if isinstance(remaining_iteration_budget, int) and remaining_iteration_budget <= 0:
            return True

        if self._has_no_actionable_evidence_need(top_gap, next_evidence_need):
            return True

        if (
            assessment.get("finding_maturity") == "stable"
            and assessment.get("support_strength") == "strong_enough"
        ):
            return True

        if not self._available_tool_names(stage_input):
            return True

        return self._is_latency_constrained(stage_input) and top_gap.get(
            "gap_severity"
        ) != "blocking"


    def _memory_acquisition_available(
        self,
        stage_input: ResearchStageInput,
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> bool:
        """Return whether memory-backed acquisition is a valid candidate."""

        if not self._has_memory_capability(stage_input):
            return False
        if next_evidence_need.get("freshness_requirement") == "fresh_required":
            return False
        return top_gap.get("gap_nature") not in {"stale", "imbalanced"}


    def _external_acquisition_available(
        self,
        stage_input: ResearchStageInput,
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> bool:
        """Return whether external acquisition is a valid candidate."""

        if not self._external_source_families(stage_input):
            return False

        gap_nature = top_gap.get("gap_nature")
        freshness_requirement = next_evidence_need.get("freshness_requirement")
        desired_evidence_kind = next_evidence_need.get("desired_evidence_kind")
        return (
            gap_nature in {"missing", "stale", "imbalanced"}
            or freshness_requirement == "fresh_required"
            or desired_evidence_kind
            in {
                "direct_fact",
                "comparison_evidence",
                "fresh_status_evidence",
            }
        )


    def _select_action_mode(
        self,
        candidate_action_modes: list[ResearchActionMode],
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> ResearchActionMode:
        """Select one action mode from rule-gated candidates."""

        if len(candidate_action_modes) == 1:
            return candidate_action_modes[0]

        if (
            _EXTERNAL_ACTION_MODE in candidate_action_modes
            and (
                next_evidence_need.get("freshness_requirement") == "fresh_required"
                or top_gap.get("gap_nature") == "stale"
            )
        ):
            return _EXTERNAL_ACTION_MODE

        if _MEMORY_ACTION_MODE in candidate_action_modes:
            return _MEMORY_ACTION_MODE

        if _EXTERNAL_ACTION_MODE in candidate_action_modes:
            return _EXTERNAL_ACTION_MODE

        return _REFINE_ACTION_MODE


    def _build_action_request(
        self,
        action_mode: ResearchActionMode,
        stage_input: ResearchStageInput,
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Build the stage-local action request envelope for acquisition modes."""

        if action_mode == _REFINE_ACTION_MODE:
            return None

        allowed_source_families = self._allowed_source_families_for_action(
            action_mode,
            stage_input,
        )
        return {
            "action_mode": action_mode,
            "evidence_acquisition_intent": {
                "target_scope": self._action_target_scope(top_gap, next_evidence_need),
                "target_problem": self._action_target_problem(
                    stage_input,
                    top_gap,
                    next_evidence_need,
                ),
                "gap_context": {
                    "gap_scope": top_gap.get("gap_scope"),
                    "gap_nature": top_gap.get("gap_nature"),
                    "gap_severity": top_gap.get("gap_severity"),
                    "gap_summary": top_gap.get("gap_summary"),
                },
                "evidence_goal": next_evidence_need.get("need_purpose"),
                "evidence_shape": {
                    "desired_evidence_kind": next_evidence_need.get(
                        "desired_evidence_kind"
                    ),
                    "freshness_requirement": next_evidence_need.get(
                        "freshness_requirement"
                    ),
                    "breadth": "normal",
                },
                "constraints": {
                    "allowed_source_families": allowed_source_families,
                    "preferred_source_families": allowed_source_families,
                    "blocked_source_families": [],
                    "max_results": 5,
                    "scope_restrictions": stage_input.scope_restrictions,
                },
                "success_hint": next_evidence_need.get("need_summary")
                or top_gap.get("gap_actionability"),
            },
            "fallback_policy": (
                "fallback_within_same_family"
                if action_mode == _MEMORY_ACTION_MODE
                else "fallback_to_broader_search"
            ),
            "preferred_tool": None,
        }


    def _allowed_source_families_for_action(
        self,
        action_mode: ResearchActionMode,
        stage_input: ResearchStageInput,
    ) -> list[str]:
        """Resolve source family constraints for the stage-local action request."""

        if action_mode == _MEMORY_ACTION_MODE:
            return [FamilyName.RESEARCH_KNOWLEDGE_RECALL.value]
        if action_mode == _EXTERNAL_ACTION_MODE:
            return self._external_source_families(stage_input)
        return []


    def _action_target_scope(
        self,
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> str | None:
        """Return the most specific target scope available for the action intent."""

        return (
            next_evidence_need.get("need_target")
            or top_gap.get("gap_target")
            or next_evidence_need.get("need_scope")
            or top_gap.get("gap_scope")
        )


    def _action_target_problem(
        self,
        stage_input: ResearchStageInput,
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> str:
        """Return a concrete problem statement for later acquisition."""

        return (
            next_evidence_need.get("need_summary")
            or top_gap.get("gap_summary")
            or stage_input.user_goal
            or stage_input.original_query
        )


    def _action_rationale(
        self,
        action_mode: ResearchActionMode,
        stage_input: ResearchStageInput,
        assessment: dict[str, Any],
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> str:
        """Build a short deterministic rationale for observability."""

        if action_mode == _MEMORY_ACTION_MODE:
            return "当前 gap 可由已有研究记忆低成本推进，且 freshness 未要求 fresh_required，因此优先 memory-backed acquisition。"
        if action_mode == _EXTERNAL_ACTION_MODE:
            return "当前 gap 或 evidence need 更依赖新鲜、直接、比较型或外部可追溯材料，因此进入 external acquisition。"
        if not self._available_tool_names(stage_input):
            return "当前 runtime 未声明 acquisition capability，因此本轮基于已有 state refine。"
        if self._has_no_actionable_evidence_need(top_gap, next_evidence_need):
            return "当前 top_gap / next_evidence_need 表示没有可推进的 actionable gap，因此不发起 acquisition。"
        if (
            assessment.get("finding_maturity") == "stable"
            and assessment.get("support_strength") == "strong_enough"
        ):
            return "当前 finding 已稳定且支撑强度足够，因此更适合 refine existing state。"
        if self._is_latency_constrained(stage_input) and top_gap.get(
            "gap_severity"
        ) != "blocking":
            return "当前 latency budget 较紧且 gap 不是 blocking，因此避免新增 acquisition。"
        return "当前没有满足约束的 acquisition path，因此基于已有 state refine。"


    def _has_memory_capability(self, stage_input: ResearchStageInput) -> bool:
        """Return whether runtime capabilities include a memory-related path."""

        available_tool_names = self._available_tool_names(stage_input)
        return bool(available_tool_names & _MEMORY_CAPABILITY_NAMES)


    def _external_source_families(self, stage_input: ResearchStageInput) -> list[str]:
        """Map external runtime capabilities to retrieval family names."""

        available_tool_names = self._available_tool_names(stage_input)
        if available_tool_names & _EXTERNAL_ALL_CAPABILITY_NAMES:
            return [
                FamilyName.DOCS_SEARCH.value,
                FamilyName.PAPER_SEARCH.value,
                FamilyName.WEB_SEARCH.value,
            ]

        families: list[str] = []
        for tool_name in available_tool_names:
            family = _EXTERNAL_CAPABILITY_FAMILY_MAP.get(tool_name)
            if family and family not in families:
                families.append(family)
        return families


    def _is_latency_constrained(self, stage_input: ResearchStageInput) -> bool:
        """Return whether runtime latency budget should discourage acquisition."""

        return (
            stage_input.latency_budget_ms is not None
            and stage_input.latency_budget_ms <= 1000
        )
