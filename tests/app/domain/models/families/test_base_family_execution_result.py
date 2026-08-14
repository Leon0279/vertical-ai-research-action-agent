"""Shared base family execution result tests."""

import pytest
from pydantic import ValidationError

from app.domain.enums import AcquisitionStatus
from app.domain.models import (
    ArxivPaperSearchToolResult,
    BaseFamilyExecutionResult,
    DocsSearchFamilyResult,
    PaperSearchFamilyResult,
    ResearchKnowledgeRecallFamilyResult,
    WebSearchFamilyResult,
)


def test_family_results_inherit_shared_base_type() -> None:
    docs_result = DocsSearchFamilyResult(
        acquisition_status=AcquisitionStatus.SUCCESS,
        normalized_items=[],
    )
    paper_result = PaperSearchFamilyResult(
        acquisition_status=AcquisitionStatus.NO_RESULT,
        normalized_items=[],
    )
    web_result = WebSearchFamilyResult(
        acquisition_status=AcquisitionStatus.PARTIAL_SUCCESS,
        normalized_items=[],
    )
    memory_result = ResearchKnowledgeRecallFamilyResult(
        acquisition_status=AcquisitionStatus.FAILED,
        normalized_items=[],
    )

    assert isinstance(docs_result, BaseFamilyExecutionResult)
    assert isinstance(paper_result, BaseFamilyExecutionResult)
    assert isinstance(web_result, BaseFamilyExecutionResult)
    assert isinstance(memory_result, BaseFamilyExecutionResult)


def test_family_results_keep_selected_family_defaults() -> None:
    assert DocsSearchFamilyResult(acquisition_status=AcquisitionStatus.SUCCESS).selected_family == "docs_search"
    assert PaperSearchFamilyResult(acquisition_status=AcquisitionStatus.SUCCESS).selected_family == "paper_search"
    assert WebSearchFamilyResult(acquisition_status=AcquisitionStatus.SUCCESS).selected_family == "web_search"
    assert (
        ResearchKnowledgeRecallFamilyResult(acquisition_status=AcquisitionStatus.SUCCESS).selected_family
        == "research_knowledge_recall"
    )


def test_acquisition_status_enum_keeps_string_compatibility() -> None:
    assert AcquisitionStatus.SUCCESS == "success"

    tool_result = ArxivPaperSearchToolResult(acquisition_status=AcquisitionStatus.SUCCESS)
    family_result = DocsSearchFamilyResult(acquisition_status=AcquisitionStatus.PARTIAL_SUCCESS)

    assert tool_result.acquisition_status == AcquisitionStatus.SUCCESS
    assert family_result.acquisition_status == AcquisitionStatus.PARTIAL_SUCCESS
    assert tool_result.model_dump(mode="json")["acquisition_status"] == "success"
    assert (
        family_result.model_dump(mode="json")["acquisition_status"]
        == "partial_success"
    )


def test_acquisition_status_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError):
        ArxivPaperSearchToolResult(acquisition_status="unknown")

    with pytest.raises(ValidationError):
        DocsSearchFamilyResult(acquisition_status="unknown")
