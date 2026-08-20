"""Research stage model tests."""

import pytest
from pydantic import ValidationError

from app.domain.models import ResearchStageInput, ResearchStageResult, SourceReference


def test_research_stage_input_minimal_construction() -> None:
    stage_input = ResearchStageInput(original_query="Compare RAG and web search.")

    assert stage_input.original_query == "Compare RAG and web search."
    assert stage_input.constraints == []
    assert stage_input.plan == []
    assert stage_input.sub_questions == []
    assert stage_input.owner_user_id is None
    assert stage_input.initial_evidence_strategy == []
    assert stage_input.active_decision_summary is None
    assert stage_input.current_action_status is None
    assert stage_input.current_bottleneck_summary is None
    assert stage_input.research_support == []
    assert stage_input.decision_support == []
    assert stage_input.action_support == []
    assert stage_input.available_tools == []
    dumped = stage_input.model_dump()
    assert "existing_evidence_summary" not in dumped
    assert "external_evidence_support" not in dumped


def test_research_stage_result_defaults_do_not_write_back_content() -> None:
    result = ResearchStageResult()

    assert result.research_status == "no_result"
    assert result.retrieved_evidence_refs == []
    assert result.evidence_summary is None
    assert result.intermediate_findings == []
    assert result.open_questions == []
    assert result.executed_iteration_count == 0
    assert result.error_info is None


def test_research_stage_result_uses_typed_source_references() -> None:
    result = ResearchStageResult(
        retrieved_evidence_refs=[
            SourceReference(
                source_type="document",
                source_url="https://docs.example/ref",
                title="Docs reference",
            )
        ]
    )

    assert result.retrieved_evidence_refs[0].source_url == "https://docs.example/ref"
    assert result.model_dump(mode="json")["retrieved_evidence_refs"] == [
        {
            "source_type": "document",
            "sub_source_type": None,
            "source_id": None,
            "source_id_type": None,
            "source_url": "https://docs.example/ref",
            "title": "Docs reference",
            "authors": [],
            "publisher": None,
            "published_at": None,
            "retrieved_at": None,
            "evidence_span": None,
            "citation_text": None,
            "source_ref_id": None,
            "metadata": {},
        }
    ]


def test_research_stage_result_rejects_legacy_string_evidence_refs() -> None:
    with pytest.raises(ValidationError):
        ResearchStageResult(retrieved_evidence_refs=["https://docs.example/ref"])
