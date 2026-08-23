"""Research Executor 内部的确定性 action decision 协作者。"""

from __future__ import annotations

from app.domain.enums import FamilyName
from app.domain.models import ResearchStageInput
from app.services.executor.models.research_action_request import ResearchActionRequest
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMNextEvidenceNeedPayload,
    _LLMResearchAssessmentPayload,
    _LLMResearchGapPayload,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)
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
    "docs": FamilyName.DOCS_SEARCH,
    "docs_search": FamilyName.DOCS_SEARCH,
    "llms_txt_docs_search_v1": FamilyName.DOCS_SEARCH,
    "paper": FamilyName.PAPER_SEARCH,
    "paper_search": FamilyName.PAPER_SEARCH,
    "arxiv_paper_search_v1": FamilyName.PAPER_SEARCH,
    "web": FamilyName.WEB_SEARCH,
    "web_search": FamilyName.WEB_SEARCH,
    "tavily_web_search_v1": FamilyName.WEB_SEARCH,
}
_EXTERNAL_ALL_CAPABILITY_NAMES = {"external", "external_acquisition"}


class ResearchActionDecider(ResearchExecutorCollaboratorSupport):
    """根据 assessment 与 runtime 约束选择本轮是否进入 acquisition。"""

    async def decide(
        self,
        stage_input: ResearchStageInput,
        run_state: ResearchExecutorRunState,
    ) -> bool:
        """依据当前强类型 assessment 产出本轮 action decision。"""

        assessment = self._required_assessment(run_state)
        top_gap = self._required_top_gap(run_state)
        next_evidence_need = self._required_next_evidence_need(run_state)
        iteration = run_state.require_current_iteration()
        candidate_action_modes = self._candidate_action_modes(
            stage_input,
            iteration.remaining_iteration_budget,
            assessment,
            top_gap,
            next_evidence_need,
        )
        action_mode = self._select_action_mode(
            candidate_action_modes,
            top_gap,
            next_evidence_need,
        )
        iteration.candidate_action_modes = candidate_action_modes
        iteration.action_mode = action_mode
        iteration.action_rationale = self._action_rationale(
            action_mode,
            stage_input,
            assessment,
            top_gap,
            next_evidence_need,
        )
        iteration.action_request = self._build_action_request(
            action_mode,
            stage_input,
            top_gap,
            next_evidence_need,
        )
        return action_mode != _REFINE_ACTION_MODE

    def _candidate_action_modes(
        self,
        stage_input: ResearchStageInput,
        remaining_iteration_budget: int,
        assessment: _LLMResearchAssessmentPayload,
        top_gap: _LLMResearchGapPayload,
        next_evidence_need: _LLMNextEvidenceNeedPayload,
    ) -> list[ResearchActionMode]:
        """应用确定性 gate，生成本轮可行的 action mode。"""

        if self._must_refine_from_existing_state(
            stage_input,
            remaining_iteration_budget,
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
        remaining_iteration_budget: int,
        assessment: _LLMResearchAssessmentPayload,
        top_gap: _LLMResearchGapPayload,
        next_evidence_need: _LLMNextEvidenceNeedPayload,
    ) -> bool:
        """判断 acquisition 是否明确无必要或不可用。"""

        if remaining_iteration_budget <= 0:
            return True
        if self._has_no_actionable_evidence_need(top_gap, next_evidence_need):
            return True
        if (
            assessment.finding_maturity == "stable"
            and assessment.support_strength == "strong_enough"
        ):
            return True
        if not self._available_tool_names(stage_input):
            return True
        return self._is_latency_constrained(stage_input) and top_gap.gap_severity != "blocking"

    def _memory_acquisition_available(
        self,
        stage_input: ResearchStageInput,
        top_gap: _LLMResearchGapPayload,
        next_evidence_need: _LLMNextEvidenceNeedPayload,
    ) -> bool:
        """判断 memory-backed acquisition 是否是有效候选。"""

        if not self._has_memory_capability(stage_input):
            return False
        if next_evidence_need.freshness_requirement == "fresh_required":
            return False
        return top_gap.gap_nature not in {"stale", "imbalanced"}

    def _external_acquisition_available(
        self,
        stage_input: ResearchStageInput,
        top_gap: _LLMResearchGapPayload,
        next_evidence_need: _LLMNextEvidenceNeedPayload,
    ) -> bool:
        """判断 external acquisition 是否是有效候选。"""

        if not self._external_source_families(stage_input):
            return False
        return (
            top_gap.gap_nature in {"missing", "stale", "imbalanced"}
            or next_evidence_need.freshness_requirement == "fresh_required"
            or next_evidence_need.desired_evidence_kind
            in {"direct_fact", "comparison_evidence", "fresh_status_evidence"}
        )

    def _select_action_mode(
        self,
        candidate_action_modes: list[ResearchActionMode],
        top_gap: _LLMResearchGapPayload,
        next_evidence_need: _LLMNextEvidenceNeedPayload,
    ) -> ResearchActionMode:
        """从规则筛选后的候选中选择单个 action mode。"""

        if len(candidate_action_modes) == 1:
            return candidate_action_modes[0]
        if (
            _EXTERNAL_ACTION_MODE in candidate_action_modes
            and (
                next_evidence_need.freshness_requirement == "fresh_required"
                or top_gap.gap_nature == "stale"
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
        top_gap: _LLMResearchGapPayload,
        next_evidence_need: _LLMNextEvidenceNeedPayload,
    ) -> ResearchActionRequest | None:
        """构造 acquisition path 所需的强类型 action request。"""

        if action_mode == _REFINE_ACTION_MODE:
            return None
        allowed_source_families = self._allowed_source_families_for_action(
            action_mode,
            stage_input,
        )
        return ResearchActionRequest(
            action_mode=action_mode,
            target_scope=self._action_target_scope(top_gap, next_evidence_need),
            target_problem=self._action_target_problem(
                stage_input,
                top_gap,
                next_evidence_need,
            ),
            gap_scope=top_gap.gap_scope,
            gap_nature=top_gap.gap_nature,
            gap_severity=top_gap.gap_severity,
            gap_summary=top_gap.gap_summary,
            evidence_goal=next_evidence_need.need_purpose,
            desired_evidence_kind=next_evidence_need.desired_evidence_kind,
            freshness_requirement=next_evidence_need.freshness_requirement,
            allowed_source_families=allowed_source_families,
            preferred_source_families=list(allowed_source_families),
            scope_restrictions=list(stage_input.scope_restrictions),
            success_hint=(
                next_evidence_need.need_summary or top_gap.gap_actionability
            ),
            fallback_policy=(
                "fallback_within_same_family"
                if action_mode == _MEMORY_ACTION_MODE
                else "fallback_to_broader_search"
            ),
        )

    def _allowed_source_families_for_action(
        self,
        action_mode: ResearchActionMode,
        stage_input: ResearchStageInput,
    ) -> list[FamilyName]:
        """解析本轮 action request 的 retrieval family 约束。"""

        if action_mode == _MEMORY_ACTION_MODE:
            return [FamilyName.RESEARCH_KNOWLEDGE_RECALL]
        if action_mode == _EXTERNAL_ACTION_MODE:
            return self._external_source_families(stage_input)
        return []

    def _action_target_scope(
        self,
        top_gap: _LLMResearchGapPayload,
        next_evidence_need: _LLMNextEvidenceNeedPayload,
    ) -> str | None:
        """返回 action intent 可用的最具体目标范围。"""

        return (
            next_evidence_need.need_target
            or top_gap.gap_target
            or next_evidence_need.need_scope
            or top_gap.gap_scope
        )

    def _action_target_problem(
        self,
        stage_input: ResearchStageInput,
        top_gap: _LLMResearchGapPayload,
        next_evidence_need: _LLMNextEvidenceNeedPayload,
    ) -> str:
        """返回后续 acquisition 要解决的具体问题。"""

        return (
            next_evidence_need.need_summary
            or top_gap.gap_summary
            or stage_input.user_goal
            or stage_input.original_query
        )

    def _action_rationale(
        self,
        action_mode: ResearchActionMode,
        stage_input: ResearchStageInput,
        assessment: _LLMResearchAssessmentPayload,
        top_gap: _LLMResearchGapPayload,
        next_evidence_need: _LLMNextEvidenceNeedPayload,
    ) -> str:
        """构造可解释的确定性 action rationale。"""

        if action_mode == _MEMORY_ACTION_MODE:
            return "当前 gap 可由已有研究记忆低成本推进，且 freshness 未要求 fresh_required，因此优先 memory-backed acquisition。"
        if action_mode == _EXTERNAL_ACTION_MODE:
            return "当前 gap 或 evidence need 更依赖新鲜、直接、比较型或外部可追溯材料，因此进入 external acquisition。"
        if not self._available_tool_names(stage_input):
            return "当前 runtime 未声明 acquisition capability，因此本轮基于已有 state refine。"
        if self._has_no_actionable_evidence_need(top_gap, next_evidence_need):
            return "当前 top_gap / next_evidence_need 表示没有可推进的 actionable gap，因此不发起 acquisition。"
        if (
            assessment.finding_maturity == "stable"
            and assessment.support_strength == "strong_enough"
        ):
            return "当前 finding 已稳定且支撑强度足够，因此更适合 refine existing state。"
        if self._is_latency_constrained(stage_input) and top_gap.gap_severity != "blocking":
            return "当前 latency budget 较紧且 gap 不是 blocking，因此避免新增 acquisition。"
        return "当前没有满足约束的 acquisition path，因此基于已有 state refine。"

    def _required_assessment(
        self,
        run_state: ResearchExecutorRunState,
    ) -> _LLMResearchAssessmentPayload:
        """返回当前 assessment；缺失时说明 Step 1 尚未完成。"""

        if run_state.current_assessment is None:
            raise ValueError("current_assessment is required before action decision.")
        return run_state.current_assessment

    def _required_top_gap(
        self,
        run_state: ResearchExecutorRunState,
    ) -> _LLMResearchGapPayload:
        """返回当前 top gap；缺失时说明 Step 1 尚未完成。"""

        if run_state.top_gap is None:
            raise ValueError("top_gap is required before action decision.")
        return run_state.top_gap

    def _required_next_evidence_need(
        self,
        run_state: ResearchExecutorRunState,
    ) -> _LLMNextEvidenceNeedPayload:
        """返回当前 evidence need；缺失时说明 Step 1 尚未完成。"""

        if run_state.next_evidence_need is None:
            raise ValueError("next_evidence_need is required before action decision.")
        return run_state.next_evidence_need

    def _has_memory_capability(self, stage_input: ResearchStageInput) -> bool:
        """判断 runtime capability 是否包含 memory acquisition 路径。"""

        return bool(self._available_tool_names(stage_input) & _MEMORY_CAPABILITY_NAMES)

    def _external_source_families(
        self,
        stage_input: ResearchStageInput,
    ) -> list[FamilyName]:
        """将外部 runtime capability 映射为 retrieval family enum。"""

        available_tool_names = self._available_tool_names(stage_input)
        if available_tool_names & _EXTERNAL_ALL_CAPABILITY_NAMES:
            return [
                FamilyName.DOCS_SEARCH,
                FamilyName.PAPER_SEARCH,
                FamilyName.WEB_SEARCH,
            ]
        families: list[FamilyName] = []
        for tool_name in available_tool_names:
            family = _EXTERNAL_CAPABILITY_FAMILY_MAP.get(tool_name)
            if family is not None and family not in families:
                families.append(family)
        return families

    def _is_latency_constrained(self, stage_input: ResearchStageInput) -> bool:
        """判断 latency budget 是否应抑制非阻塞 acquisition。"""

        return (
            stage_input.latency_budget_ms is not None
            and stage_input.latency_budget_ms <= 1000
        )
