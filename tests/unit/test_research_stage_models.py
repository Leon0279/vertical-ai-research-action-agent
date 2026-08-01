"""Research stage model tests."""

from app.domain.models import ResearchStageInput, ResearchStageResult


def test_research_stage_input_minimal_construction() -> None:
    stage_input = ResearchStageInput(original_query="Compare RAG and web search.")

    assert stage_input.original_query == "Compare RAG and web search."
    assert stage_input.constraints == []
    assert stage_input.plan == []
    assert stage_input.sub_questions == []
    assert stage_input.owner_user_id is None
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
