"""Family selection service tests."""

from __future__ import annotations

import asyncio

from app.domain.enums import ActionMode
from app.domain.models import EvidenceShape, FamilySelectionRequest
from app.services.tool_execution_layer.family_selection_service import FamilySelectionService


def _select(request: FamilySelectionRequest):
    return asyncio.run(FamilySelectionService().select_family(request))


def test_external_acquisition_defaults_to_docs_search() -> None:
    result = _select(FamilySelectionRequest(target_problem="Find official API guidance"))

    assert result.selection_status == "selected"
    assert result.selected_family == "docs_search"
    assert result.candidate_families == ["docs_search", "paper_search", "web_search"]
    assert "selected_tool" not in result.model_dump()


def test_memory_backed_acquisition_selects_research_knowledge_recall() -> None:
    result = _select(
        FamilySelectionRequest(
            target_problem="Reuse prior pgvector governance conclusion",
            action_mode=ActionMode.MEMORY_BACKED_ACQUISITION,
        )
    )

    assert result.selection_status == "selected"
    assert result.selected_family == "research_knowledge_recall"


def test_action_mode_accepts_legacy_string_and_dumps_string_value() -> None:
    request = FamilySelectionRequest(
        target_problem="Reuse prior pgvector governance conclusion",
        action_mode="memory_backed_acquisition",
    )

    assert request.action_mode == ActionMode.MEMORY_BACKED_ACQUISITION
    assert ActionMode.EXTERNAL_ACQUISITION == "external_acquisition"
    assert request.model_dump(mode="json")["action_mode"] == "memory_backed_acquisition"


def test_fresh_status_evidence_selects_web_search() -> None:
    result = _select(
        FamilySelectionRequest(
            target_problem="Check current API status",
            evidence_shape=EvidenceShape(
                desired_evidence_kind="status_evidence",
                freshness_requirement="fresh_required",
                breadth="normal",
            ),
        )
    )

    assert result.selected_family == "web_search"


def test_comparison_evidence_selects_paper_search() -> None:
    result = _select(
        FamilySelectionRequest(
            target_problem="Compare agentic RAG methods",
            evidence_goal="rebalance_comparison",
            evidence_shape=EvidenceShape(
                desired_evidence_kind="comparison_evidence",
                freshness_requirement="normal",
                breadth="broad",
            ),
        )
    )

    assert result.selected_family == "paper_search"


def test_preferred_source_families_raise_available_family() -> None:
    result = _select(
        FamilySelectionRequest(
            target_problem="Find broad public context",
            preferred_source_families=["web_search"],
        )
    )

    assert result.selected_family == "web_search"
    assert result.ranked_candidate_families[0] == "web_search"


def test_allowed_blocked_and_available_families_filter_candidates() -> None:
    result = _select(
        FamilySelectionRequest(
            target_problem="Find implementation docs",
            available_families=["docs_search", "paper_search"],
            allowed_source_families=["docs_search", "web_search"],
            blocked_source_families=["docs_search"],
        )
    )

    assert result.selection_status == "no_match"
    assert result.selected_family is None
    assert result.candidate_families == []


def test_available_families_limits_selection() -> None:
    result = _select(
        FamilySelectionRequest(
            target_problem="Find official API guidance",
            available_families=["web_search"],
        )
    )

    assert result.selection_status == "selected"
    assert result.selected_family == "web_search"
    assert result.candidate_families == ["web_search"]


def test_empty_target_problem_returns_failed() -> None:
    result = _select(FamilySelectionRequest(target_problem="  "))

    assert result.selection_status == "failed"
    assert result.selected_family is None
    assert result.error_info == "target_problem must not be empty."


def test_selection_trace_and_summary_include_routing_details() -> None:
    result = _select(
        FamilySelectionRequest(
            target_problem="Find current implementation guidance",
            evidence_goal="improve_actionability",
            evidence_shape=EvidenceShape(breadth="narrow"),
            preferred_source_families=["docs_search"],
        )
    )

    assert result.selection_summary["selected_family"] == "docs_search"
    assert result.selection_summary["policy"] == "deterministic_family_ranking_v1"
    assert result.selection_trace["candidate_families"] == result.candidate_families
    assert result.selection_trace["ranked_candidate_families"] == result.ranked_candidate_families
    assert result.selection_trace["evidence_shape"]["breadth"] == "narrow"
