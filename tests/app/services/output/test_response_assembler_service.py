"""Response assembler service tests."""

import asyncio

from app.domain.enums.task_type import TaskType
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models import Citation, ExecutionContext, RunningState, RuntimeContext
from app.services.output.response_assembler_service import ResponseAssemblerService


def test_response_assembler_includes_session_metadata() -> None:
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval methods.",
            task_type=TaskType.COMPARISON.value,
        ),
        runtime_context=RuntimeContext(
            request_id="trace-123",
            user_id="user-1",
            session_id="session-123",
            session_id_generated=True,
            tool_registry_version="default-retrieval-v1",
        ),
    )
    context.runtime_context.stage_history.append("request_intake")

    output = asyncio.run(ResponseAssemblerService().assemble(context))

    assert output.trace_id == "trace-123"
    assert output.task_type == TaskType.COMPARISON
    assert output.workflow_pattern == WorkflowPattern.COMPARISON
    assert output.metadata == {
        "session_id": "session-123",
        "session_id_generated": True,
        "research_status": None,
        "research_iteration_count": 0,
        "tool_registry_version": "default-retrieval-v1",
    }
    assert output.stage_history == ["request_intake"]


def test_response_assembler_converts_running_state_outputs() -> None:
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval methods.",
            task_type=TaskType.COMPARISON.value,
            research_status="partial_success",
            research_iteration_count=2,
            final_answer="Use the simpler retrieval baseline first, then evaluate quality.",
            final_summary="Prefer the simple baseline first.",
            final_recommendation="Use the simpler retrieval baseline first.",
            action_items=["Run a small evaluation."],
            citations=[
                Citation(
                    source="https://example.test/retrieval-baseline",
                    note="Supports the baseline-first recommendation.",
                )
            ],
            confidence="medium",
            caveats=["Needs validation on production-like traffic."],
        ),
        runtime_context=RuntimeContext(
            request_id="trace-123",
            user_id="user-1",
            session_id="session-123",
            tool_registry_version="default-retrieval-v1",
        ),
    )

    output = asyncio.run(ResponseAssemblerService().assemble(context))

    assert output.answer == "Use the simpler retrieval baseline first, then evaluate quality."
    assert output.summary == "Prefer the simple baseline first."
    assert output.recommendation == "Use the simpler retrieval baseline first."
    assert [item.title for item in output.action_items] == ["Run a small evaluation."]
    assert output.citations == [
        Citation(
            source="https://example.test/retrieval-baseline",
            note="Supports the baseline-first recommendation.",
        )
    ]
    assert output.confidence == 0.5
    assert output.caveats == ["Needs validation on production-like traffic."]
    assert output.metadata["research_status"] == "partial_success"
    assert output.metadata["research_iteration_count"] == 2
    assert output.metadata["tool_registry_version"] == "default-retrieval-v1"


def test_response_assembler_prefers_routed_workflow_pattern() -> None:
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval methods.",
            task_type=TaskType.COMPARISON.value,
            workflow_pattern=WorkflowPattern.RECOMMENDATION,
        ),
        runtime_context=RuntimeContext(
            request_id="trace-123",
            user_id="user-1",
            session_id="session-123",
        ),
    )

    output = asyncio.run(ResponseAssemblerService().assemble(context))

    assert output.task_type == TaskType.COMPARISON
    assert output.workflow_pattern == WorkflowPattern.RECOMMENDATION


def test_response_assembler_uses_safe_fallbacks_when_conclusion_fields_missing() -> None:
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval methods.",
            evidence_summary="processed_evidence_count=1",
        ),
        runtime_context=RuntimeContext(
            request_id="trace-123",
            user_id="user-1",
            session_id="session-123",
        ),
    )

    output = asyncio.run(ResponseAssemblerService().assemble(context))

    assert output.answer == (
        "当前尚未生成完整最终答案，但已有研究摘要可供参考："
        "processed_evidence_count=1"
    )
    assert output.summary == "当前尚未形成最终答案摘要。"
    assert output.citations == []
    assert output.caveats == []
