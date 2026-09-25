"""Context Memory Loader stage model tests。"""

from app.domain.models import (
    ContextItem,
    ContextMemoryLoaderStageInput,
    ContextMemoryLoaderStageResult,
)


def test_context_memory_loader_stage_input_supports_minimal_construction() -> None:
    stage_input = ContextMemoryLoaderStageInput(
        user_id="user-1",
        session_id="session-1",
        original_query="What changed?",
    )

    assert stage_input.project_scope_id is None
    assert stage_input.task_type is None
    assert stage_input.user_goal is None
    assert stage_input.task_framing is None
    assert stage_input.model_dump(mode="json")["user_id"] == "user-1"


def test_context_memory_loader_stage_result_defaults_do_not_write_context() -> None:
    result = ContextMemoryLoaderStageResult()

    assert result.task_framing is None
    assert result.project_context_summary is None
    assert result.active_decision_summary is None
    assert result.current_action_status is None
    assert result.constraints == []
    assert result.open_questions == []
    assert result.session_support == []
    assert result.project_support == []
    assert result.decision_support == []
    assert result.action_support == []
    assert result.policy_support == []
    assert result.research_support == []


def test_context_memory_loader_stage_result_serializes_context_items() -> None:
    result = ContextMemoryLoaderStageResult(
        research_support=[
            ContextItem(
                id="knowledge-1",
                source_type="research_knowledge_memory",
                summary="Reusable research summary.",
                priority=6,
            )
        ]
    )

    assert result.model_dump(mode="json")["research_support"] == [
        {
            "id": "knowledge-1",
            "source_type": "research_knowledge_memory",
            "scope_id": None,
            "summary": "Reusable research summary.",
            "priority": 6,
            "freshness_tag": None,
            "confidence": None,
            "can_assimilate_to_state": False,
            "usage_hint": None,
        }
    ]
