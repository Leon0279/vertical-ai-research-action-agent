"""Shared base family execution result tests."""

from app.domain.models import (
    BaseFamilyExecutionResult,
    DocsSearchFamilyResult,
    PaperSearchFamilyResult,
    ResearchKnowledgeRecallFamilyResult,
    WebSearchFamilyResult,
)


def test_family_results_inherit_shared_base_type() -> None:
    docs_result = DocsSearchFamilyResult(
        acquisition_status="success",
        normalized_items=[],
    )
    paper_result = PaperSearchFamilyResult(
        acquisition_status="no_result",
        normalized_items=[],
    )
    web_result = WebSearchFamilyResult(
        acquisition_status="partial_success",
        normalized_items=[],
    )
    memory_result = ResearchKnowledgeRecallFamilyResult(
        acquisition_status="failed",
        normalized_items=[],
    )

    assert isinstance(docs_result, BaseFamilyExecutionResult)
    assert isinstance(paper_result, BaseFamilyExecutionResult)
    assert isinstance(web_result, BaseFamilyExecutionResult)
    assert isinstance(memory_result, BaseFamilyExecutionResult)


def test_family_results_keep_selected_family_defaults() -> None:
    assert DocsSearchFamilyResult(acquisition_status="success").selected_family == "docs_search"
    assert PaperSearchFamilyResult(acquisition_status="success").selected_family == "paper_search"
    assert WebSearchFamilyResult(acquisition_status="success").selected_family == "web_search"
    assert (
        ResearchKnowledgeRecallFamilyResult(acquisition_status="success").selected_family
        == "research_knowledge_recall"
    )
