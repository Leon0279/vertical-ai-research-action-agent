"""Pipeline stage ordering tests."""

import asyncio
import json

from app.domain.models import (
    ContextItem,
    ExecutionContext,
    RequestContext,
    ResearchStageInput,
    ResearchStageResult,
    RunningState,
    RuntimeContext,
    SourceReference,
    SupplementalContext,
)
from app.orchestration import pipeline_dependencies
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


class _FakeZhipuLLMClient:
    async def generate_text(self, prompt: str) -> str:
        if "最终结论生成调用" in prompt:
            return json.dumps(
                {
                    "final_answer": "默认 pipeline 测试生成的最终答案。",
                    "final_summary": "默认 pipeline 测试摘要。",
                    "final_recommendation": None,
                    "action_items": [],
                    "citations": [],
                    "confidence": "low",
                    "caveats": [],
                },
                ensure_ascii=False,
            )
        if "中间研究发现更新" in prompt:
            return json.dumps(
                {
                    "intermediate_findings": [],
                    "finding_caveats": [],
                },
                ensure_ascii=False,
            )
        if "研究迭代结果评估" in prompt:
            return json.dumps(
                {
                    "top_gap_progress": "resolved",
                    "evidence_gain": "limited_gain",
                    "finding_progress": "improved_but_not_stable",
                    "residual_uncertainty": "low",
                    "proposed_iteration_outcome": "stop",
                    "proposed_outcome_rationale": "默认 pipeline 测试选择收束。",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "assessment": {
                    "coverage_status": "not_covered",
                    "support_strength": "insufficient_support",
                    "finding_maturity": "tentative",
                    "assessment_summary": "默认 pipeline 测试中的 fake assessment。",
                },
                "identified_gaps": [],
                "top_gap": {
                    "gap_scope": "objective_level",
                    "gap_nature": "none",
                    "gap_severity": "none",
                    "gap_summary": "默认 pipeline 测试没有 actionable gap。",
                    "gap_target": None,
                    "gap_actionability": None,
                },
                "next_evidence_need": {
                    "need_scope": "objective_level",
                    "need_target": None,
                    "need_purpose": "none",
                    "desired_evidence_kind": "none",
                    "freshness_requirement": "none",
                    "minimum_support_requirement": "none",
                    "need_summary": "默认 pipeline 测试不触发新的 evidence need。",
                },
                "prioritization_summary": "默认 pipeline 测试不选择 top gap。",
            },
            ensure_ascii=False,
        )


def test_pipeline_stage_order(monkeypatch) -> None:
    monkeypatch.setattr(pipeline_dependencies, "ZhipuLLMClient", _FakeZhipuLLMClient)
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
    existing_evidence_ref = SourceReference(
        source_type="web_page",
        source_url="https://existing.test/ref",
        title="Existing evidence",
    )
    duplicate_existing_evidence_ref = SourceReference(
        source_type="web_page",
        source_url="https://existing.test/ref",
        title="Existing evidence duplicate",
    )
    new_evidence_ref = SourceReference(
        source_type="web_page",
        source_url="https://new.test/ref",
        title="New evidence",
    )
    research_support = ContextItem(
        id="ctx-research",
        source_type="research_memory",
        summary="Existing research says retrieval quality depends on freshness.",
        priority=8,
    )
    decision_support = ContextItem(
        id="ctx-decision",
        source_type="decision_memory",
        summary="Existing decision prefers memory-backed retrieval first.",
        priority=7,
    )
    action_support = ContextItem(
        id="ctx-action",
        source_type="action_memory",
        summary="Current action is blocked on freshness evidence.",
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
            retrieved_evidence_refs=[existing_evidence_ref],
            open_questions=["Existing open question."],
        ),
        supplemental_context=SupplementalContext(
            research_support=[research_support],
            decision_support=[decision_support],
            action_support=[action_support],
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
            duplicate_existing_evidence_ref,
            new_evidence_ref,
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
        owner_user_id="user-1",
        project_context_summary="The project ships a research agent.",
        plan=["Compare memory-backed and web-backed retrieval."],
        sub_questions=["When should memory be preferred?"],
        comparison_candidates=["memory", "web"],
        information_gaps=["Need freshness tradeoffs."],
        existing_intermediate_findings=["Existing finding."],
        research_support=[research_support],
        decision_support=[decision_support],
        action_support=[action_support],
        available_tools=["docs_search"],
        latency_budget_ms=1000,
        iteration_budget=2,
        scope_restrictions=["project_only"],
    )
    assert context.running_state.retrieved_evidence_refs == [
        existing_evidence_ref,
        new_evidence_ref,
    ]
    assert context.running_state.evidence_summary == "Updated evidence summary."
    assert context.running_state.intermediate_findings == ["Existing finding.", "New finding."]
    assert context.running_state.open_questions == [
        "Existing open question.",
        "New open question.",
    ]


def test_empty_research_stage_result_does_not_clear_existing_state() -> None:
    evidence_ref = SourceReference(source_type="document", source_id="ref-1")
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Keep prior research state.",
            retrieved_evidence_refs=[evidence_ref],
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

    assert context.running_state.retrieved_evidence_refs == [evidence_ref]
    assert context.running_state.evidence_summary == "Keep this summary."
    assert context.running_state.intermediate_findings == ["Keep this finding."]
    assert context.running_state.open_questions == ["Keep this question."]


def test_research_stage_result_deduplicates_typed_source_ids() -> None:
    existing_ref = SourceReference(
        source_type="paper",
        source_id="2501.12345v2",
        source_id_type="arxiv_id",
        title="Existing paper title",
    )
    duplicate_ref = SourceReference(
        source_type="paper",
        source_id="2501.12345v2",
        source_id_type="arxiv_id",
        title="Updated paper title",
    )
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Keep typed refs unique.",
            retrieved_evidence_refs=[existing_ref],
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
            research_executor=_FakeResearchExecutor(
                ResearchStageResult(retrieved_evidence_refs=[duplicate_ref])
            ),
            conclusion_generator=object(),
            memory_distiller=object(),
            memory_persistence=object(),
            session_continuity_manager=object(),
            response_assembler=object(),
        )
    )

    asyncio.run(pipeline._research(context))

    assert context.running_state.retrieved_evidence_refs == [existing_ref]
