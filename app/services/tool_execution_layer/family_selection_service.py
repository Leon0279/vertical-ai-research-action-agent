"""Family selection service for the tool execution layer."""

from __future__ import annotations

from app.domain.enums import ActionMode
from app.domain.models import EvidenceShape, FamilySelectionRequest, FamilySelectionResult
from app.services.tool_execution_layer.contracts.family_selection_service_protocol import (
    FamilySelectionServiceProtocol,
)


class FamilySelectionService(FamilySelectionServiceProtocol):
    """Select a retrieval family without resolving a concrete tool."""

    _MEMORY_FAMILIES = ("research_knowledge_recall",)
    _EXTERNAL_FAMILIES = ("docs_search", "paper_search", "web_search")
    _SUPPORTED_FAMILIES = _MEMORY_FAMILIES + _EXTERNAL_FAMILIES
    _EXTERNAL_FALLBACK_ORDER = ("docs_search", "web_search", "paper_search")
    _ANY_FALLBACK_ORDER = ("research_knowledge_recall", "docs_search", "web_search", "paper_search")

    async def select_family(self, request: FamilySelectionRequest) -> FamilySelectionResult:
        """Select the best family for the given acquisition intent."""

        normalized_request = self._normalize_request(request)
        if not normalized_request.target_problem:
            return self._failed_result(
                normalized_request=normalized_request,
                error_info="target_problem must not be empty.",
            )

        initial_scope = self._initial_scope(normalized_request.action_mode)
        available_filtered = self._filter_available(
            families=initial_scope,
            available_families=normalized_request.available_families,
        )
        allowed_filtered = self._filter_allowed(
            families=available_filtered,
            allowed_families=normalized_request.allowed_source_families,
        )
        candidate_families = [
            family
            for family in allowed_filtered
            if family not in set(normalized_request.blocked_source_families)
        ]

        if not candidate_families:
            return self._no_match_result(
                normalized_request=normalized_request,
                initial_scope=initial_scope,
                available_filtered=available_filtered,
                allowed_filtered=allowed_filtered,
            )

        ranked_candidate_families = self._rank_families(
            families=candidate_families,
            request=normalized_request,
        )
        selected_family = ranked_candidate_families[0]

        return FamilySelectionResult(
            candidate_families=candidate_families,
            ranked_candidate_families=ranked_candidate_families,
            selected_family=selected_family,
            selection_status="selected",
            selection_summary={
                "selected_family": selected_family,
                "candidate_count": len(candidate_families),
                "action_mode": normalized_request.action_mode,
                "policy": "deterministic_family_ranking_v1",
            },
            selection_trace={
                "target_problem": normalized_request.target_problem,
                "action_mode": normalized_request.action_mode,
                "initial_scope": initial_scope,
                "available_families": normalized_request.available_families,
                "after_available_filter": available_filtered,
                "allowed_source_families": normalized_request.allowed_source_families,
                "after_allowed_filter": allowed_filtered,
                "blocked_source_families": normalized_request.blocked_source_families,
                "candidate_families": candidate_families,
                "preferred_source_families": normalized_request.preferred_source_families,
                "evidence_goal": normalized_request.evidence_goal,
                "evidence_shape": (
                    normalized_request.evidence_shape.model_dump()
                    if normalized_request.evidence_shape
                    else None
                ),
                "task_type": normalized_request.task_type,
                "task_framing": normalized_request.task_framing,
                "evidence_strategy": normalized_request.evidence_strategy,
                "ranked_candidate_families": ranked_candidate_families,
            },
            error_info=None,
        )

    def _normalize_request(self, request: FamilySelectionRequest) -> FamilySelectionRequest:
        return FamilySelectionRequest(
            target_problem=request.target_problem.strip(),
            action_mode=request.action_mode,
            evidence_goal=(request.evidence_goal or "").strip() or None,
            evidence_shape=request.evidence_shape,
            task_type=(request.task_type or "").strip() or None,
            task_framing=(request.task_framing or "").strip() or None,
            evidence_strategy=(request.evidence_strategy or "").strip() or None,
            allowed_source_families=self._normalize_family_list(request.allowed_source_families),
            preferred_source_families=self._normalize_family_list(request.preferred_source_families),
            blocked_source_families=self._normalize_family_list(request.blocked_source_families),
            available_families=self._normalize_family_list(request.available_families),
        )

    def _normalize_family_list(self, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped or stripped in seen:
                continue
            normalized.append(stripped)
            seen.add(stripped)
        return normalized

    def _initial_scope(self, action_mode: ActionMode) -> list[str]:
        if action_mode == ActionMode.MEMORY_BACKED_ACQUISITION:
            return list(self._MEMORY_FAMILIES)
        if action_mode == ActionMode.ANY:
            return list(self._SUPPORTED_FAMILIES)
        return list(self._EXTERNAL_FAMILIES)

    def _filter_available(self, *, families: list[str], available_families: list[str]) -> list[str]:
        if not available_families:
            return families
        available = set(available_families)
        return [family for family in families if family in available]

    def _filter_allowed(self, *, families: list[str], allowed_families: list[str]) -> list[str]:
        if not allowed_families:
            return families
        allowed = set(allowed_families)
        return [family for family in families if family in allowed]

    def _rank_families(
        self,
        *,
        families: list[str],
        request: FamilySelectionRequest,
    ) -> list[str]:
        fallback_order = self._fallback_order(request.action_mode)
        fallback_index = {family: index for index, family in enumerate(fallback_order)}
        scores = {family: 0 for family in families}

        for family in request.preferred_source_families:
            if family in scores:
                scores[family] += 100

        self._apply_evidence_goal_scores(scores=scores, evidence_goal=request.evidence_goal)
        self._apply_evidence_shape_scores(scores=scores, evidence_shape=request.evidence_shape)
        self._apply_contextual_scores(
            scores=scores,
            task_framing=request.task_framing,
            evidence_strategy=request.evidence_strategy,
        )

        return sorted(
            families,
            key=lambda family: (
                -scores[family],
                fallback_index.get(family, len(fallback_order)),
                family,
            ),
        )

    def _fallback_order(self, action_mode: ActionMode) -> tuple[str, ...]:
        if action_mode == ActionMode.MEMORY_BACKED_ACQUISITION:
            return self._MEMORY_FAMILIES
        if action_mode == ActionMode.ANY:
            return self._ANY_FALLBACK_ORDER
        return self._EXTERNAL_FALLBACK_ORDER

    def _apply_evidence_goal_scores(
        self,
        *,
        scores: dict[str, int],
        evidence_goal: str | None,
    ) -> None:
        if evidence_goal in {"improve_actionability", "establish_coverage"}:
            self._add_score(scores, "docs_search", 35)
            self._add_score(scores, "web_search", 10)
        if evidence_goal in {"rebalance_comparison", "resolve_conflict"}:
            self._add_score(scores, "paper_search", 35)
            self._add_score(scores, "web_search", 20)
            self._add_score(scores, "docs_search", 10)
        if evidence_goal == "refresh_status":
            self._add_score(scores, "web_search", 40)
            self._add_score(scores, "docs_search", 25)
        if evidence_goal == "strengthen_support":
            self._add_score(scores, "docs_search", 20)
            self._add_score(scores, "paper_search", 15)
            self._add_score(scores, "web_search", 10)
        if evidence_goal == "resolve_ambiguity":
            self._add_score(scores, "docs_search", 25)
            self._add_score(scores, "web_search", 20)

    def _apply_evidence_shape_scores(
        self,
        *,
        scores: dict[str, int],
        evidence_shape: EvidenceShape | None,
    ) -> None:
        if evidence_shape is None:
            return

        desired_kind = evidence_shape.desired_evidence_kind
        freshness = evidence_shape.freshness_requirement
        breadth = evidence_shape.breadth

        if desired_kind == "direct_fact":
            self._add_score(scores, "docs_search", 35)
            self._add_score(scores, "web_search", 15)
        elif desired_kind == "status_evidence":
            self._add_score(scores, "web_search", 40)
            self._add_score(scores, "docs_search", 25)
        elif desired_kind == "comparison_evidence":
            self._add_score(scores, "paper_search", 35)
            self._add_score(scores, "docs_search", 15)
            self._add_score(scores, "web_search", 10)
        elif desired_kind == "disambiguating_evidence":
            self._add_score(scores, "docs_search", 25)
            self._add_score(scores, "web_search", 20)
        elif desired_kind == "supporting_evidence":
            self._add_score(scores, "docs_search", 15)
            self._add_score(scores, "paper_search", 15)
            self._add_score(scores, "web_search", 10)

        if freshness == "fresh_required":
            self._add_score(scores, "web_search", 40)
            self._add_score(scores, "docs_search", 25)
        elif freshness == "fresh_preferred":
            self._add_score(scores, "web_search", 15)
            self._add_score(scores, "docs_search", 10)

        if breadth == "narrow":
            self._add_score(scores, "docs_search", 20)
        elif breadth == "broad":
            self._add_score(scores, "web_search", 20)
            self._add_score(scores, "paper_search", 10)

    def _apply_contextual_scores(
        self,
        *,
        scores: dict[str, int],
        task_framing: str | None,
        evidence_strategy: str | None,
    ) -> None:
        combined = " ".join(value for value in [task_framing, evidence_strategy] if value)
        if not combined:
            return
        normalized = combined.lower()
        if any(term in normalized for term in ["memory", "recall", "reuse", "existing knowledge"]):
            self._add_score(scores, "research_knowledge_recall", 30)
        if any(term in normalized for term in ["comparison", "method", "research"]):
            self._add_score(scores, "paper_search", 15)
        if any(term in normalized for term in ["latest", "fresh", "current", "status"]):
            self._add_score(scores, "web_search", 15)

    def _add_score(self, scores: dict[str, int], family: str, score: int) -> None:
        if family in scores:
            scores[family] += score

    def _failed_result(
        self,
        *,
        normalized_request: FamilySelectionRequest,
        error_info: str,
    ) -> FamilySelectionResult:
        return FamilySelectionResult(
            candidate_families=[],
            ranked_candidate_families=[],
            selected_family=None,
            selection_status="failed",
            selection_summary={
                "selected_family": None,
                "candidate_count": 0,
                "action_mode": normalized_request.action_mode,
                "policy": "deterministic_family_ranking_v1",
            },
            selection_trace={
                "target_problem": normalized_request.target_problem,
                "action_mode": normalized_request.action_mode,
                "family_selection_error": error_info,
            },
            error_info=error_info,
        )

    def _no_match_result(
        self,
        *,
        normalized_request: FamilySelectionRequest,
        initial_scope: list[str],
        available_filtered: list[str],
        allowed_filtered: list[str],
    ) -> FamilySelectionResult:
        error_info = "No matching source family is available for this request."
        return FamilySelectionResult(
            candidate_families=[],
            ranked_candidate_families=[],
            selected_family=None,
            selection_status="no_match",
            selection_summary={
                "selected_family": None,
                "candidate_count": 0,
                "action_mode": normalized_request.action_mode,
                "policy": "deterministic_family_ranking_v1",
            },
            selection_trace={
                "target_problem": normalized_request.target_problem,
                "action_mode": normalized_request.action_mode,
                "initial_scope": initial_scope,
                "available_families": normalized_request.available_families,
                "after_available_filter": available_filtered,
                "allowed_source_families": normalized_request.allowed_source_families,
                "after_allowed_filter": allowed_filtered,
                "blocked_source_families": normalized_request.blocked_source_families,
                "candidate_families": [],
                "family_selection_error": error_info,
            },
            error_info=error_info,
        )
