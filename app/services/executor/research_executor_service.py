"""Research stage executor scaffold."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.domain.enums import ActionMode, FamilyName
from app.domain.models import (
    EvidenceProcessingRequest,
    EvidenceShape,
    ProcessedEvidenceUnit,
    ResearchStageInput,
    ResearchStageResult,
    ToolExecutionLayerRequest,
    ToolExecutionLayerResult,
)
from app.domain.models.context.context_item import ContextItem
from app.services.evidence.contracts.evidence_processing_service_protocol import (
    EvidenceProcessingServiceProtocol,
)
from app.services.executor.contracts.research_executor_protocol import ResearchExecutorProtocol
from app.services.tool_execution_layer.contracts.tool_execution_layer_service_protocol import (
    ToolExecutionLayerServiceProtocol,
)

ResearchIterationOutcome = Literal["continue", "stop", "degrade"]
ResearchActionMode = Literal[
    "refine_from_existing_state",
    "memory_backed_acquisition",
    "external_acquisition",
]
ResearchCoverageStatus = Literal["covered", "partially_covered", "not_covered"]
ResearchSupportStrength = Literal[
    "strong_enough",
    "weak_support",
    "conflicting_support",
    "insufficient_support",
]
ResearchFindingMaturity = Literal["tentative", "partially_stable", "stable", "blocked"]
ResearchGapScope = Literal[
    "objective_level",
    "sub_question_level",
    "comparison_level",
    "candidate_level",
    "dimension_level",
    "finding_level",
    "recommendation_readiness_level",
]
ResearchGapNature = Literal[
    "missing",
    "weak",
    "ambiguous",
    "conflicting",
    "imbalanced",
    "stale",
    "not_actionable",
    "none",
]
ResearchGapSeverity = Literal["blocking", "important", "optional", "none"]
ResearchNeedPurpose = Literal[
    "establish_coverage",
    "strengthen_support",
    "resolve_ambiguity",
    "resolve_conflict",
    "rebalance_comparison",
    "refresh_status",
    "improve_actionability",
    "none",
]
ResearchDesiredEvidenceKind = Literal[
    "direct_fact",
    "stronger_supporting_evidence",
    "disambiguating_evidence",
    "comparison_evidence",
    "fresh_status_evidence",
    "decision_supporting_evidence",
    "none",
]
ResearchFreshnessRequirement = Literal["normal", "fresh_preferred", "fresh_required", "none"]
ResearchMinimumSupportRequirement = Literal[
    "any_relevant_signal",
    "moderate_support",
    "strong_support",
    "none",
]

_REFINE_ACTION_MODE: ResearchActionMode = "refine_from_existing_state"
_MEMORY_ACTION_MODE: ResearchActionMode = "memory_backed_acquisition"
_EXTERNAL_ACTION_MODE: ResearchActionMode = "external_acquisition"

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
_EXTERNAL_ALL_CAPABILITY_NAMES = {
    "external",
    "external_acquisition",
}


class _LLMResearchAssessmentPayload(BaseModel):
    """Service-private schema for the LLM's current-state assessment."""

    model_config = ConfigDict(extra="forbid")

    coverage_status: ResearchCoverageStatus = Field(min_length=1)
    support_strength: ResearchSupportStrength = Field(min_length=1)
    finding_maturity: ResearchFindingMaturity = Field(min_length=1)
    assessment_summary: str = Field(min_length=1)


class _LLMResearchGapPayload(BaseModel):
    """Service-private schema for one LLM-identified research gap."""

    model_config = ConfigDict(extra="forbid")

    gap_scope: ResearchGapScope = Field(min_length=1)
    gap_nature: ResearchGapNature = Field(min_length=1)
    gap_severity: ResearchGapSeverity = Field(min_length=1)
    gap_summary: str = Field(min_length=1)
    gap_target: str | None = None
    gap_actionability: str | None = None


class _LLMNextEvidenceNeedPayload(BaseModel):
    """Service-private schema for the current iteration's next evidence need."""

    model_config = ConfigDict(extra="forbid")

    need_scope: ResearchGapScope = Field(min_length=1)
    need_target: str | None = None
    need_purpose: ResearchNeedPurpose = Field(min_length=1)
    desired_evidence_kind: ResearchDesiredEvidenceKind = Field(min_length=1)
    freshness_requirement: ResearchFreshnessRequirement = Field(min_length=1)
    minimum_support_requirement: ResearchMinimumSupportRequirement = Field(min_length=1)
    need_summary: str = Field(min_length=1)


class _LLMResearchAssessmentAndGapsPayload(BaseModel):
    """Strict LLM output payload for the full 4.4 research decision block."""

    model_config = ConfigDict(extra="forbid")

    assessment: _LLMResearchAssessmentPayload
    identified_gaps: list[_LLMResearchGapPayload] = Field(default_factory=list)
    top_gap: _LLMResearchGapPayload
    next_evidence_need: _LLMNextEvidenceNeedPayload
    prioritization_summary: str = Field(min_length=1)


class ResearchExecutorService(ResearchExecutorProtocol):
    """Research stage executor.

    The old context-mutating retrieval skeleton has intentionally been removed.
    Future iterations should implement the research loop against ResearchStageInput
    and return ResearchStageResult for the pipeline to write back.
    """

    def __init__(
        self,
        *,
        llm_client: LLMClientProtocol,
        tool_execution_layer_service: ToolExecutionLayerServiceProtocol,
        evidence_processing_service: EvidenceProcessingServiceProtocol,
    ) -> None:
        if llm_client is None:
            raise ValueError("ResearchExecutorService requires an llm_client.")
        if tool_execution_layer_service is None:
            raise ValueError(
                "ResearchExecutorService requires a tool_execution_layer_service."
            )
        if evidence_processing_service is None:
            raise ValueError(
                "ResearchExecutorService requires an evidence_processing_service."
            )
        self._llm_client = llm_client
        self._tool_execution_layer_service = tool_execution_layer_service
        self._evidence_processing_service = evidence_processing_service

    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        """Run bounded scaffolded canonical research iterations."""

        working_state: dict[str, Any] = {
            "stage_input": stage_input,
            "processed_evidence_units": [],
            "evidence_coverage_map": {},
            "identified_gaps": [],
            "intermediate_findings": list(stage_input.existing_intermediate_findings),
        }
        max_iterations = self._max_iterations(stage_input)
        executed_iteration_count = 0
        outcome: ResearchIterationOutcome = "continue"

        while outcome == "continue" and executed_iteration_count < max_iterations:
            working_state["iteration_index"] = executed_iteration_count + 1
            working_state["remaining_iteration_budget"] = (
                max_iterations - executed_iteration_count
            )
            await self._assess_research_state_and_select_next_evidence_need(
                stage_input,
                working_state,
            )
            should_acquire_candidate_material = await self._decide_whether_external_action_is_needed(
                stage_input,
                working_state,
            )

            if should_acquire_candidate_material:
                await self._acquire_candidate_material(stage_input, working_state)
                await self._process_candidate_material_into_usable_evidence(
                    stage_input,
                    working_state,
                )

            await self._update_stage_local_working_state(stage_input, working_state)
            await self._produce_or_refine_intermediate_findings(stage_input, working_state)
            outcome = await self._evaluate_iteration_outcome(stage_input, working_state)
            executed_iteration_count += 1

        return ResearchStageResult(executed_iteration_count=executed_iteration_count)

    def _max_iterations(self, stage_input: ResearchStageInput) -> int:
        """Resolve the bounded loop budget from stage input only."""

        if stage_input.iteration_budget is None or stage_input.iteration_budget < 1:
            return 1
        return stage_input.iteration_budget

    async def _assess_research_state_and_select_next_evidence_need(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Run LLD 4.4: assess state, identify gaps, and select the next evidence need."""

        prompt = self._build_research_assessment_prompt(stage_input, working_state)
        llm_output = await self._llm_client.generate_text(prompt)
        payload = self._parse_research_assessment_output(llm_output)

        working_state["current_assessment"] = payload.assessment.model_dump(mode="json")
        working_state["identified_gaps"] = [
            gap.model_dump(mode="json") for gap in payload.identified_gaps
        ]
        working_state["top_gap"] = payload.top_gap.model_dump(mode="json")
        working_state["next_evidence_need"] = payload.next_evidence_need.model_dump(
            mode="json"
        )
        working_state["prioritization_summary"] = payload.prioritization_summary

    async def _decide_whether_external_action_is_needed(
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

    def _has_no_actionable_evidence_need(
        self,
        top_gap: dict[str, Any],
        next_evidence_need: dict[str, Any],
    ) -> bool:
        """Detect the no-op style payload defined by the 4.4 LLM output contract."""

        return (
            top_gap.get("gap_nature") == "none"
            or top_gap.get("gap_severity") == "none"
            or next_evidence_need.get("need_purpose") == "none"
            or next_evidence_need.get("desired_evidence_kind") == "none"
        )

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

    def _available_tool_names(self, stage_input: ResearchStageInput) -> set[str]:
        """Normalize runtime capability names for deterministic matching."""

        return {
            tool_name.strip().lower()
            for tool_name in stage_input.available_tools
            if tool_name.strip()
        }

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

    def _working_state_dict(
        self,
        working_state: dict[str, Any],
        key: str,
    ) -> dict[str, Any]:
        """Return a dict value from working state, defaulting to an empty dict."""

        value = working_state.get(key)
        if isinstance(value, dict):
            return value
        return {}

    async def _acquire_candidate_material(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 4. Acquire candidate material through the appropriate action path."""

        request = self._tool_execution_layer_request(stage_input, working_state)
        result = await self._tool_execution_layer_service.execute(request)
        working_state["tool_execution_request"] = request
        working_state["tool_execution_result"] = result
        working_state["candidate_materials"] = list(result.normalized_items)

    async def _process_candidate_material_into_usable_evidence(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 5. Process candidate material into usable evidence representation."""

        _ = stage_input
        tool_execution_result = working_state.get("tool_execution_result")
        if not isinstance(tool_execution_result, ToolExecutionLayerResult):
            raise ValueError(
                "tool_execution_result is required before evidence processing."
            )

        request = EvidenceProcessingRequest.from_tool_execution_result(
            tool_execution_result
        )
        result = await self._evidence_processing_service.process(request)
        working_state["evidence_processing_request"] = request
        working_state["evidence_processing_result"] = result
        processed_evidence_units = working_state.setdefault(
            "processed_evidence_units",
            [],
        )
        if isinstance(processed_evidence_units, list):
            processed_evidence_units.extend(result.processed_evidence_units)

    def _tool_execution_layer_request(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> ToolExecutionLayerRequest:
        """Project the stage-local action request into TEL's public request model."""

        action_request = working_state.get("action_request")
        if not isinstance(action_request, dict):
            raise ValueError("action_request is required before material acquisition.")

        action_mode = self._tel_action_mode(action_request.get("action_mode"))
        intent = self._action_request_intent(action_request)
        next_evidence_need = self._working_state_dict(
            working_state,
            "next_evidence_need",
        )
        top_gap = self._working_state_dict(working_state, "top_gap")
        constraints = self._action_request_constraints(intent)
        max_results = self._positive_int(constraints.get("max_results"), default=5)
        allowed_source_families = self._family_names(
            constraints.get("allowed_source_families", [])
        )
        preferred_source_families = self._family_names(
            constraints.get("preferred_source_families", [])
        )
        blocked_source_families = self._family_names(
            constraints.get("blocked_source_families", [])
        )

        return ToolExecutionLayerRequest(
            target_problem=self._required_text(
                intent.get("target_problem"),
                fallback=stage_input.user_goal or stage_input.original_query,
                field_name="target_problem",
            ),
            action_mode=action_mode,
            evidence_goal=self._optional_text(next_evidence_need.get("need_purpose")),
            evidence_shape=self._tel_evidence_shape_from_next_evidence_need(
                next_evidence_need,
                intent.get("evidence_shape"),
            ),
            task_framing=stage_input.task_framing,
            allowed_source_families=allowed_source_families,
            preferred_source_families=preferred_source_families,
            blocked_source_families=blocked_source_families,
            available_families=allowed_source_families,
            success_hint=self._success_hint(intent, next_evidence_need, top_gap),
            preferred_tool=self._optional_text(action_request.get("preferred_tool")),
            max_search_results=max_results,
            max_content_fetches=3,
            owner_user_id=stage_input.owner_user_id,
            project_scope_id=stage_input.project_scope_id,
            allowed_visibility_scopes=self._allowed_visibility_scopes(stage_input),
            memory_recall_limit=max_results,
            retry_budget=1,
            fallback_policy=(
                self._optional_text(action_request.get("fallback_policy"))
                or "fallback_within_same_family"
            ),
            timeout_limit_ms=self._positive_optional_int(
                stage_input.latency_budget_ms
            ),
        )

    def _tel_action_mode(self, action_mode: Any) -> ActionMode:
        """Map Research Executor action mode into TEL acquisition mode."""

        if action_mode == _MEMORY_ACTION_MODE:
            return ActionMode.MEMORY_BACKED_ACQUISITION
        if action_mode == _EXTERNAL_ACTION_MODE:
            return ActionMode.EXTERNAL_ACQUISITION
        raise ValueError(f"Unsupported acquisition action mode: {action_mode!r}.")

    def _action_request_intent(self, action_request: dict[str, Any]) -> dict[str, Any]:
        """Return the action request's evidence acquisition intent."""

        intent = action_request.get("evidence_acquisition_intent")
        if not isinstance(intent, dict):
            raise ValueError("action_request.evidence_acquisition_intent is required.")
        return intent

    def _action_request_constraints(self, intent: dict[str, Any]) -> dict[str, Any]:
        """Return the action request constraints dict."""

        constraints = intent.get("constraints")
        if isinstance(constraints, dict):
            return constraints
        return {}

    def _tel_evidence_shape_from_next_evidence_need(
        self,
        next_evidence_need: dict[str, Any],
        action_evidence_shape: Any,
    ) -> EvidenceShape:
        """Map Research Executor evidence need semantics into TEL EvidenceShape."""

        desired_kind = self._optional_text(
            next_evidence_need.get("desired_evidence_kind")
        )
        tel_desired_kind = self._tel_desired_evidence_kind(desired_kind)

        freshness_requirement = self._optional_text(
            next_evidence_need.get("freshness_requirement")
        )
        if freshness_requirement == "none":
            freshness_requirement = "normal"

        breadth = "normal"
        if isinstance(action_evidence_shape, dict):
            breadth = self._optional_text(action_evidence_shape.get("breadth")) or "normal"

        return EvidenceShape(
            desired_evidence_kind=tel_desired_kind,
            freshness_requirement=freshness_requirement or "normal",
            breadth=breadth,
        )

    def _tel_desired_evidence_kind(self, desired_kind: str | None) -> str:
        """Return the TEL retrieval-facing evidence kind for a research need kind."""

        kind_mapping = {
            "direct_fact": "direct_fact",
            "stronger_supporting_evidence": "supporting_evidence",
            "disambiguating_evidence": "disambiguating_evidence",
            "comparison_evidence": "comparison_evidence",
            "fresh_status_evidence": "status_evidence",
            "decision_supporting_evidence": "supporting_evidence",
        }
        if desired_kind == "none":
            raise ValueError(
                "desired_evidence_kind='none' should not enter Tool Execution Layer."
            )
        try:
            return kind_mapping[desired_kind or ""]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported desired_evidence_kind for TEL mapping: {desired_kind!r}."
            ) from exc

    def _family_names(self, values: Any) -> list[FamilyName]:
        """Convert internal action-request family strings into FamilyName values."""

        if not isinstance(values, list):
            return []

        families: list[FamilyName] = []
        for value in values:
            try:
                family = FamilyName(value)
            except ValueError as exc:
                raise ValueError(f"Unsupported source family: {value!r}.") from exc
            if family not in families:
                families.append(family)
        return families

    def _success_hint(
        self,
        intent: dict[str, Any],
        next_evidence_need: dict[str, Any],
        top_gap: dict[str, Any],
    ) -> str | None:
        """Return a compact success hint for TEL query generation."""

        return (
            self._optional_text(intent.get("success_hint"))
            or self._optional_text(next_evidence_need.get("need_summary"))
            or self._optional_text(top_gap.get("gap_summary"))
        )

    def _allowed_visibility_scopes(self, stage_input: ResearchStageInput) -> list[str]:
        """Return memory visibility scopes for TEL requests."""

        if stage_input.project_scope_id:
            return ["user", "project"]
        return ["user"]

    def _positive_int(self, value: Any, *, default: int) -> int:
        """Return value when it is a positive int, otherwise the provided default."""

        if isinstance(value, int) and value > 0:
            return value
        return default

    def _positive_optional_int(self, value: Any) -> int | None:
        """Return a positive integer value or None."""

        if isinstance(value, int) and value > 0:
            return value
        return None

    def _required_text(
        self,
        value: Any,
        *,
        fallback: str,
        field_name: str,
    ) -> str:
        """Return stripped text, falling back to a required non-empty value."""

        text = self._optional_text(value) or self._optional_text(fallback)
        if text is None:
            raise ValueError(f"{field_name} is required for material acquisition.")
        return text

    def _optional_text(self, value: Any) -> str | None:
        """Return a stripped non-empty string or None."""

        if not isinstance(value, str):
            return None
        return value.strip() or None

    async def _update_stage_local_working_state(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 6. Merge current iteration outputs into stage-local working state."""

        _ = stage_input
        _ = working_state

    async def _produce_or_refine_intermediate_findings(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> None:
        """Step 7. Produce or refine intermediate findings from the working state."""

        _ = stage_input
        _ = working_state

    async def _evaluate_iteration_outcome(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> ResearchIterationOutcome:
        """Step 8. Evaluate whether the research stage should continue, stop, or degrade."""

        _ = stage_input
        _ = working_state
        return "stop"

    def _build_research_assessment_prompt(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> str:
        """Build the mandatory LLM prompt for research state assessment."""

        prompt_input = self._research_assessment_prompt_input(stage_input, working_state)
        return (
            "你正在执行一次“研究状态判断”任务。\n\n"
            "这是一次无状态调用。\n"
            "你不能依赖任何未出现在本 prompt 中的项目文档、代码、历史对话或系统上下文。\n"
            "你只能根据下面的任务说明和最后给出的输入 JSON 做判断。\n\n"
            "你的输出不是给用户看的最终回答。\n"
            "你的输出是给后续程序使用的结构化 JSON，用来描述：\n"
            "1. 当前研究状态是否已经被材料覆盖；\n"
            "2. 当前仍有哪些未解决的信息缺口；\n"
            "3. 当前轮最应该优先处理的一个缺口；\n"
            "4. 下一步最需要补充哪类 evidence。\n\n"
            "输入 JSON 分为以下区域：\n\n"
            "1. task_context\n"
            "- current_research_objective：当前研究目标，是本次判断的主对象。\n"
            "- task_type：任务类型。不同任务类型对 evidence 的要求不同，例如 comparison 更关注平衡覆盖，"
            "tracking 更关注新鲜度，recommendation / action planning 更关注可执行性。\n"
            "- task_framing：当前任务的高层表达方式，用于帮助理解研究问题。\n"
            "- constraints：当前研究必须遵守的限制条件。\n"
            "- project_context_summary：项目背景摘要。它只用于判断材料是否适合当前项目语境，"
            "不得用来扩大研究范围。\n\n"
            "2. planning_guidance\n"
            "- plan：上游给出的高层计划，只作为参考，不是必须逐条执行的脚本。\n"
            "- sub_questions：上游拆解出的子问题，用于判断哪些问题已有覆盖、哪些仍缺材料。\n"
            "- comparison_candidates：如果任务涉及比较，这里列出需要比较的对象，用于判断候选对象覆盖是否不平衡。\n"
            "这些 planning 信息只能作为边界和参考，不要改写、删除或扩展它们。\n\n"
            "3. supporting_context\n"
            "- research_support：已整理过的研究知识摘要。\n"
            "- decision_support：已整理过的决策摘要，用于判断当前研究是否受已有决策约束，或是否缺少决策支撑。\n"
            "- action_support：已整理过的行动状态摘要，用于判断当前执行状态、阻塞和下一步可执行性相关缺口。\n"
            "这些内容是摘要级支持信息，不是原始记录，不是完整资料，也不是本轮新获得的 evidence。\n"
            "你可以把它们作为判断背景，但不要把它们当作已经充分验证的事实来源。\n\n"
            "4. evidence_state\n"
            "- processed_evidence：当前已经处理成可用 evidence 的材料。\n"
            "- evidence_coverage_map：当前 evidence 对研究目标、子问题、候选对象或比较维度的覆盖情况。\n"
            "- intermediate_findings：当前已经形成的中间发现。\n"
            "这些字段是判断 coverage、support strength 和 finding maturity 的主要依据。\n\n"
            "5. gap_state\n"
            "- identified_gaps：此前已经识别出的未解决缺口。\n"
            "- top_gap：此前选出的最高优先级缺口，如果存在。\n"
            "- next_evidence_need：此前判断出的下一步 evidence need，如果存在。\n"
            "如果这些字段为空，请根据当前输入重新判断。\n"
            "如果这些字段非空，请优先复用仍然有效的缺口，不要每轮都无理由创造全新缺口。\n\n"
            "6. runtime_control\n"
            "- iteration_index：当前是第几轮研究迭代。\n"
            "- remaining_iteration_budget：当前还允许继续多少轮。\n"
            "- input_budget_pressure：当前上下文或预算压力。\n"
            "- available_capabilities：当前可用能力摘要。它只用于判断某个 evidence need 是否现实可推进，"
            "不要在输出中指定具体工具名、执行路径或 action mode。\n\n"
            "请在内部按以下顺序判断，但不要输出推理过程：\n\n"
            "1. 判断 current_research_objective 是否已经被 processed_evidence 和可信的 supporting context 基本覆盖。\n"
            "2. 判断已有材料对 intermediate_findings 的支撑强度：足够、偏弱、冲突，还是不足。\n"
            "3. 判断 intermediate_findings 的成熟度：tentative、partially_stable、stable，还是 blocked。\n"
            "4. 识别多个 unresolved gaps。gap 表示当前研究目标与已有材料支撑状态之间的差距。\n"
            "5. 从 identified_gaps 中选择当前轮唯一 top_gap。\n"
            "6. 将 top_gap 转换成 next_evidence_need，说明下一步最需要补充哪类 evidence。\n\n"
            "选择 top_gap 时请优先考虑：\n\n"
            "1. gap_severity 的通常优先级是 blocking > important > optional > none。\n"
            "2. 更直接影响 current_research_objective 的 gap 优先。\n"
            "3. 会阻碍后续结论、建议或可执行性的 gap 优先。\n"
            "4. 对 comparison 任务，导致候选对象或比较维度不平衡的 gap 优先。\n"
            "5. 对 tracking 任务，新鲜度不足或状态不明确的 gap 优先。\n"
            "6. 对 recommendation / action planning 任务，导致建议不可执行、风险不清或决策支撑不足的 gap 优先。\n"
            "7. 在当前 remaining_iteration_budget、input_budget_pressure 和 available_capabilities 下更现实可推进的 gap 优先。\n\n"
            "next_evidence_need 只描述“下一步需要补充哪类 evidence”。\n"
            "它不是搜索词，不是工具调用参数，也不是执行步骤。\n"
            "不要把 need_summary 写成可直接执行的搜索 query。\n\n"
            "如果没有值得继续推进的 actionable gap：\n"
            "- identified_gaps 可以为空数组。\n"
            "- top_gap.gap_nature 必须为 \"none\"。\n"
            "- top_gap.gap_severity 必须为 \"none\"。\n"
            "- next_evidence_need.need_purpose 必须为 \"none\"。\n"
            "- next_evidence_need.desired_evidence_kind 必须为 \"none\"。\n"
            "- 不要为了填字段而虚构新研究方向、新子问题或新证据需求。\n\n"
            "输出边界：\n"
            "- 只输出一个 JSON object。\n"
            "- 不要回答用户的原始问题。\n"
            "- 不要输出面向用户的结论、建议、行动计划或解释性段落。\n"
            "- 不要输出具体工具名、执行路径或 action mode。\n"
            "- 不要输出搜索词或工具调用参数。\n"
            "- 不要改写 task_context 或 planning_guidance 中的目标、计划、子问题、比较对象。\n"
            "- 不要基于 project_context_summary、decision_support 或 action_support 扩大研究范围。\n"
            "- 不要输出 Markdown 标题、解释文字或额外字段。\n\n"
            "JSON 必须且只能包含以下顶层字段：\n"
            "- assessment\n"
            "- identified_gaps\n"
            "- top_gap\n"
            "- next_evidence_need\n"
            "- prioritization_summary\n\n"
            "assessment 必须且只能包含：\n"
            "- coverage_status\n"
            "- support_strength\n"
            "- finding_maturity\n"
            "- assessment_summary\n\n"
            "identified_gaps 中每一项必须且只能包含：\n"
            "- gap_scope\n"
            "- gap_nature\n"
            "- gap_severity\n"
            "- gap_summary\n"
            "- gap_target\n"
            "- gap_actionability\n\n"
            "top_gap 必须且只能包含：\n"
            "- gap_scope\n"
            "- gap_nature\n"
            "- gap_severity\n"
            "- gap_summary\n"
            "- gap_target\n"
            "- gap_actionability\n\n"
            "next_evidence_need 必须且只能包含：\n"
            "- need_scope\n"
            "- need_target\n"
            "- need_purpose\n"
            "- desired_evidence_kind\n"
            "- freshness_requirement\n"
            "- minimum_support_requirement\n"
            "- need_summary\n\n"
            "允许取值：\n"
            "- coverage_status: covered | partially_covered | not_covered\n"
            "- support_strength: strong_enough | weak_support | conflicting_support | insufficient_support\n"
            "- finding_maturity: tentative | partially_stable | stable | blocked\n"
            "- gap_scope: objective_level | sub_question_level | comparison_level | candidate_level | "
            "dimension_level | finding_level | recommendation_readiness_level\n"
            "- gap_nature: missing | weak | ambiguous | conflicting | imbalanced | stale | not_actionable | none\n"
            "- gap_severity: blocking | important | optional | none\n\n"
            "- need_scope: objective_level | sub_question_level | comparison_level | candidate_level | "
            "dimension_level | finding_level | recommendation_readiness_level\n"
            "- need_purpose: establish_coverage | strengthen_support | resolve_ambiguity | resolve_conflict | "
            "rebalance_comparison | refresh_status | improve_actionability | none\n"
            "- desired_evidence_kind: direct_fact | stronger_supporting_evidence | disambiguating_evidence | "
            "comparison_evidence | fresh_status_evidence | decision_supporting_evidence | none\n"
            "- freshness_requirement: normal | fresh_preferred | fresh_required | none\n"
            "- minimum_support_requirement: any_relevant_signal | moderate_support | strong_support | none\n\n"
            "期望 JSON 形状：\n"
            "{\n"
            '  "assessment": {\n'
            '    "coverage_status": "partially_covered",\n'
            '    "support_strength": "weak_support",\n'
            '    "finding_maturity": "tentative",\n'
            '    "assessment_summary": "一句到三句中文摘要，说明当前研究状态。"\n'
            "  },\n"
            '  "identified_gaps": [\n'
            "    {\n"
            '      "gap_scope": "sub_question_level",\n'
            '      "gap_nature": "missing",\n'
            '      "gap_severity": "important",\n'
            '      "gap_summary": "缺少某个子问题的直接证据。",\n'
            '      "gap_target": "对应的子问题或比较对象；没有则为 null",\n'
            '      "gap_actionability": "后续应补充什么类型的 evidence；没有则为 null"\n'
            "    }\n"
            "  ],\n"
            '  "top_gap": {\n'
            '    "gap_scope": "sub_question_level",\n'
            '    "gap_nature": "missing",\n'
            '    "gap_severity": "important",\n'
            '    "gap_summary": "当前轮最应该优先补足的 gap。",\n'
            '    "gap_target": "对应的子问题或比较对象；没有则为 null",\n'
            '    "gap_actionability": "后续应补充什么类型的 evidence；没有则为 null"\n'
            "  },\n"
            '  "next_evidence_need": {\n'
            '    "need_scope": "sub_question_level",\n'
            '    "need_target": "对应的子问题或比较对象；没有则为 null",\n'
            '    "need_purpose": "establish_coverage",\n'
            '    "desired_evidence_kind": "direct_fact",\n'
            '    "freshness_requirement": "normal",\n'
            '    "minimum_support_requirement": "any_relevant_signal",\n'
            '    "need_summary": "当前轮最值得补充什么 evidence，以及为什么。"\n'
            "  },\n"
            '  "prioritization_summary": "说明为什么选择这个 top_gap，以及为什么这个 next_evidence_need 最值得优先推进。"\n'
            "}\n\n"
            "输入 JSON：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )

    def _research_assessment_prompt_input(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Create the JSON input shown to the assessment LLM."""

        supporting_context: dict[str, Any] = {
            "research_support": self._context_items_for_prompt(stage_input.research_support),
            "decision_support": self._context_items_for_prompt(stage_input.decision_support),
            "action_support": self._context_items_for_prompt(stage_input.action_support),
        }

        return {
            "task_context": {
                "current_research_objective": (
                    stage_input.user_goal or stage_input.original_query
                ),
                "task_type": stage_input.task_type,
                "task_framing": stage_input.task_framing,
                "constraints": stage_input.constraints,
                "project_context_summary": stage_input.project_context_summary,
            },
            "planning_guidance": {
                "plan": stage_input.plan,
                "sub_questions": stage_input.sub_questions,
                "comparison_candidates": stage_input.comparison_candidates,
            },
            "supporting_context": supporting_context,
            "evidence_state": {
                "processed_evidence": self._processed_evidence_for_prompt(
                    working_state,
                ),
                "evidence_coverage_map": working_state.get("evidence_coverage_map", {}),
                "intermediate_findings": working_state.get("intermediate_findings", []),
            },
            "gap_state": {
                "identified_gaps": working_state.get("identified_gaps", []),
                "top_gap": working_state.get("top_gap"),
                "next_evidence_need": working_state.get("next_evidence_need"),
            },
            "runtime_control": {
                "iteration_index": working_state.get("iteration_index"),
                "remaining_iteration_budget": working_state.get(
                    "remaining_iteration_budget"
                ),
                "input_budget_pressure": self._input_budget_pressure(
                    stage_input,
                    working_state,
                ),
                "available_capabilities": stage_input.available_tools,
            },
        }

    def _processed_evidence_for_prompt(
        self,
        working_state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Convert typed processed evidence units into the prompt-facing JSON shape."""

        processed_evidence_units = working_state.get("processed_evidence_units", [])
        if not isinstance(processed_evidence_units, list):
            return []

        return [
            unit.model_dump(mode="json")
            for unit in processed_evidence_units
            if isinstance(unit, ProcessedEvidenceUnit)
        ]

    def _context_items_for_prompt(self, items: list[ContextItem]) -> list[dict[str, Any]]:
        """Convert distilled context items to the small prompt-facing shape."""

        return [
            {
                "summary": item.summary,
                "source_type": item.source_type,
                "priority": item.priority,
                "freshness_tag": item.freshness_tag,
                "confidence": item.confidence,
                "usage_hint": item.usage_hint,
            }
            for item in items
        ]

    def _input_budget_pressure(
        self,
        stage_input: ResearchStageInput,
        working_state: dict[str, Any],
    ) -> str:
        """Return a coarse budget pressure hint for assessment only."""

        remaining_iterations = working_state.get("remaining_iteration_budget")
        if remaining_iterations == 1:
            return "last_iteration"
        if stage_input.latency_budget_ms is not None and stage_input.latency_budget_ms <= 1000:
            return "latency_constrained"
        return "normal"

    def _parse_research_assessment_output(
        self,
        llm_output: str,
    ) -> _LLMResearchAssessmentAndGapsPayload:
        """Parse and validate the LLM assessment JSON."""

        json_text = self._strip_json_code_fence(llm_output)
        try:
            raw_payload = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Research assessment LLM response was not valid JSON.") from exc

        try:
            return _LLMResearchAssessmentAndGapsPayload.model_validate(raw_payload)
        except ValidationError as exc:
            raise ValueError(
                "Research assessment LLM response did not match the required schema."
            ) from exc

    def _strip_json_code_fence(self, value: str) -> str:
        """Return raw JSON text, accepting common markdown fenced JSON."""

        stripped = value.strip()
        if not stripped.startswith("```"):
            return stripped

        lines = stripped.splitlines()
        if lines and lines[0].strip().lower().startswith("```json"):
            lines = lines[1:]
        elif lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
