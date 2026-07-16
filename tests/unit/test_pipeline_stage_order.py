"""Pipeline stage ordering tests."""

import asyncio

from app.domain.models import (
    ContextItem,
    ExecutionContext,
    RequestContext,
    ResearchStageInput,
    ResearchStageResult,
    RunningState,
    RuntimeContext,
    SupplementalContext,
)
from app.orchestration.pipeline_dependencies import PipelineDependencies
from app.orchestration.research_action_pipeline import build_default_pipeline
from app.orchestration.research_action_pipeline import ResearchActionPipeline


class _FakeResearchExecutor:
    def __init__(self, result: ResearchStageResult) -> None:
        self.result = result
        self.received_input: ResearchStageInput | None = None

    async def execute(self, stage_input: ResearchStageInput) -> ResearchStageResult:
        self.received_input = stage_input
        return self.result


def test_pipeline_stage_order() -> None:
    pipeline = build_default_pipeline()
    output = asyncio.run(
        pipeline.run(
            RequestContext(
                original_query="Compare RAG and agentic retrieval for production systems.",
                user_id="u-1",
                session_id="s-1",
                project_id="p-1",
            )
        )
    )
    assert output.stage_history == [
        "request_intake",
        "task_interpretation",
        "context_memory_load",
        "workflow_routing",
        "planning",
        "research",
        "conclusion",
        "memory_writeback",
        "output",
    ]


def test_research_stage_projects_input_and_applies_result() -> None:
    research_support = ContextItem(
        id="ctx-research",
        source_type="research_memory",
        summary="Existing research says retrieval quality depends on freshness.",
        priority=8,
    )
    external_support = ContextItem(
        id="ctx-external",
        source_type="tool_result",
        summary="A prior external source mentioned RAG baseline tradeoffs.",
        priority=6,
    )
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval patterns.",
            task_type="comparison",
            user_goal="Pick a retrieval strategy.",
            task_framing="engineering_tradeoff_comparison",
            constraints=["Prefer low-latency options."],
            project_scope_id="project-1",
            project_context_summary="The project ships a research agent.",
            plan=["Compare memory-backed and web-backed retrieval."],
            sub_questions=["When should memory be preferred?"],
            comparison_candidates=["memory", "web"],
            information_gaps=["Need freshness tradeoffs."],
            evidence_summary="Existing evidence summary.",
            intermediate_findings=["Existing finding."],
            retrieved_evidence_refs=["https://existing.test/ref"],
            open_questions=["Existing open question."],
        ),
        supplemental_context=SupplementalContext(
            research_support=[research_support],
            external_evidence_support=[external_support],
        ),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            available_tools=["docs_search"],
            latency_budget_ms=1000,
            iteration_budget=2,
            scope_restrictions=["project_only"],
        ),
    )
    result = ResearchStageResult(
        research_status="completed",
        retrieved_evidence_refs=[
            "https://existing.test/ref",
            "https://new.test/ref",
        ],
        evidence_summary="Updated evidence summary.",
        intermediate_findings=["Existing finding.", "New finding."],
        open_questions=["Existing open question.", "New open question."],
        executed_iteration_count=1,
    )
    fake_executor = _FakeResearchExecutor(result)
    pipeline = ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=object(),
            task_interpreter=object(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=object(),
            research_executor=fake_executor,
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            response_assembler=object(),
        )
    )

    asyncio.run(pipeline._research(context))

    assert context.runtime_context.stage_history == ["research"]
    assert fake_executor.received_input == ResearchStageInput(
        original_query="Compare retrieval patterns.",
        task_type="comparison",
        user_goal="Pick a retrieval strategy.",
        task_framing="engineering_tradeoff_comparison",
        constraints=["Prefer low-latency options."],
        project_scope_id="project-1",
        project_context_summary="The project ships a research agent.",
        plan=["Compare memory-backed and web-backed retrieval."],
        sub_questions=["When should memory be preferred?"],
        comparison_candidates=["memory", "web"],
        information_gaps=["Need freshness tradeoffs."],
        existing_evidence_summary="Existing evidence summary.",
        existing_intermediate_findings=["Existing finding."],
        research_support=[research_support],
        external_evidence_support=[external_support],
        available_tools=["docs_search"],
        latency_budget_ms=1000,
        iteration_budget=2,
        scope_restrictions=["project_only"],
    )
    assert context.running_state.retrieved_evidence_refs == [
        "https://existing.test/ref",
        "https://new.test/ref",
    ]
    assert context.running_state.evidence_summary == "Updated evidence summary."
    assert context.running_state.intermediate_findings == ["Existing finding.", "New finding."]
    assert context.running_state.open_questions == [
        "Existing open question.",
        "New open question.",
    ]


def test_empty_research_stage_result_does_not_clear_existing_state() -> None:
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Keep prior research state.",
            retrieved_evidence_refs=["ref-1"],
            evidence_summary="Keep this summary.",
            intermediate_findings=["Keep this finding."],
            open_questions=["Keep this question."],
        ),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )
    pipeline = ResearchActionPipeline(
        dependencies=PipelineDependencies(
            request_intake=object(),
            task_interpreter=object(),
            workflow_router=object(),
            decomposition_planner=object(),
            context_memory_loader=object(),
            research_executor=_FakeResearchExecutor(ResearchStageResult()),
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            response_assembler=object(),
        )
    )

    asyncio.run(pipeline._research(context))

    assert context.running_state.retrieved_evidence_refs == ["ref-1"]
    assert context.running_state.evidence_summary == "Keep this summary."
    assert context.running_state.intermediate_findings == ["Keep this finding."]
    assert context.running_state.open_questions == ["Keep this question."]
