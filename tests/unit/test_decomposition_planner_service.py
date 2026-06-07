"""Decomposition planner service tests."""

from __future__ import annotations

import asyncio

from app.domain.enums import MemoryType, PlanningDepth, TaskType, WorkflowPattern
from app.domain.models import (
    ContextItem,
    ExecutionContext,
    RunningState,
    RuntimeContext,
    SupplementalContext,
    WorkflowExecutionPolicy,
)
from app.services.planner.decomposition_planner_service import DecompositionPlannerService


def _policy(
    *,
    planning_depth: PlanningDepth,
    evidence_strategy: str = "conceptual_research",
) -> WorkflowExecutionPolicy:
    return WorkflowExecutionPolicy(
        planning_depth=planning_depth,
        evidence_strategy=evidence_strategy,
        output_emphasis="test_output",
        memory_writeback_focus=[MemoryType.RESEARCH_KNOWLEDGE],
        routing_confidence="high",
    )


def _context(
    *,
    query: str = "Explain agent memory.",
    task_type: TaskType | None = TaskType.TOPIC_EXPLORATION,
    policy: WorkflowExecutionPolicy | None = None,
    project_context_summary: str | None = "The project is in MVP stage.",
    current_action_status: str | None = None,
    supplemental_context: SupplementalContext | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(
            original_query=query,
            task_type=task_type.value if task_type else None,
            user_goal=query,
            project_scope_id="project-1",
            project_context_summary=project_context_summary,
            current_action_status=current_action_status,
            workflow_pattern=WorkflowPattern.TOPIC_EXPLORATION,
            execution_policy=policy,
        ),
        supplemental_context=supplemental_context or SupplementalContext(),
        runtime_context=RuntimeContext(
            request_id="run-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )


def test_topic_exploration_generates_shallow_plan() -> None:
    context = _context(policy=_policy(planning_depth=PlanningDepth.SHALLOW))

    asyncio.run(DecompositionPlannerService().plan(context))

    state = context.running_state
    assert state.planning_depth == PlanningDepth.SHALLOW
    assert state.plan[0] == "Objective: Explain agent memory."
    assert "Planning depth: SHALLOW" in state.plan
    assert any("key concepts" in step for step in state.plan)
    assert state.sub_questions == []
    assert state.comparison_candidates == []
    assert any("conceptual_research" in item for item in state.initial_evidence_strategy)


def test_comparison_generates_candidates_and_comparison_questions() -> None:
    context = _context(
        query="Compare Redis vs Postgres for session memory",
        task_type=TaskType.COMPARISON,
        policy=_policy(
            planning_depth=PlanningDepth.MEDIUM,
            evidence_strategy="comparative_evidence",
        ),
    )

    asyncio.run(DecompositionPlannerService().plan(context))

    state = context.running_state
    assert state.planning_depth == PlanningDepth.MEDIUM
    assert state.comparison_candidates == ["Redis", "Postgres"]
    assert any("criteria" in question for question in state.sub_questions)
    assert any("Redis" in question for question in state.sub_questions)
    assert any("tradeoffs" in item for item in state.initial_evidence_strategy)
    assert state.information_gaps == []


def test_recommendation_generates_decision_support_plan_and_actions_strategy() -> None:
    context = _context(
        query="Should I prioritize evaluation or query rewrite for my Agentic RAG MVP?",
        task_type=TaskType.RECOMMENDATION,
        policy=_policy(
            planning_depth=PlanningDepth.MEDIUM,
            evidence_strategy="decision_support",
        ),
    )
    context.running_state.current_bottleneck_summary = "The project lacks a measurable baseline."
    context.running_state.active_decision_summary = "Redis is already chosen for session memory."

    asyncio.run(DecompositionPlannerService().plan(context))

    state = context.running_state
    assert state.comparison_candidates == ["evaluation", "query rewrite"]
    assert any("recommendation" in step for step in state.plan)
    assert any("current bottleneck" in question for question in state.sub_questions)
    assert any("follow-up actions" in item for item in state.initial_evidence_strategy)
    assert any("active project decisions" in item for item in state.initial_evidence_strategy)


def test_action_planning_generates_execution_plan() -> None:
    context = _context(
        query="Plan the next implementation steps.",
        task_type=TaskType.ACTION_PLANNING,
        policy=_policy(
            planning_depth=PlanningDepth.MEDIUM,
            evidence_strategy="execution_planning",
        ),
        current_action_status="Redis session memory is implemented.",
    )

    asyncio.run(DecompositionPlannerService().plan(context))

    state = context.running_state
    assert state.comparison_candidates == []
    assert any("target outcome" in step for step in state.plan)
    assert any("dependencies" in question for question in state.sub_questions)
    assert any("sequencing" in item for item in state.initial_evidence_strategy)
    assert "Current action status is not available." not in state.information_gaps


def test_tracking_generates_update_tracking_plan() -> None:
    context = _context(
        query="Check what changed in the project status.",
        task_type=TaskType.TRACKING,
        policy=_policy(
            planning_depth=PlanningDepth.SHALLOW,
            evidence_strategy="update_tracking",
        ),
        current_action_status="Action memory adapter is pending tests.",
    )

    asyncio.run(DecompositionPlannerService().plan(context))

    state = context.running_state
    assert state.planning_depth == PlanningDepth.SHALLOW
    assert any("status" in step for step in state.plan)
    assert any("What changed" in question for question in state.sub_questions)
    assert any("fresh status" in item for item in state.initial_evidence_strategy)


def test_missing_execution_policy_falls_back_from_task_type() -> None:
    context = _context(
        query="Compare action memory and decision memory",
        task_type=TaskType.COMPARISON,
        policy=None,
    )

    asyncio.run(DecompositionPlannerService().plan(context))

    assert context.running_state.planning_depth == PlanningDepth.MEDIUM
    assert context.running_state.plan


def test_missing_comparison_candidates_records_information_gap() -> None:
    context = _context(
        query="Recommend the best next architecture improvement.",
        task_type=TaskType.RECOMMENDATION,
        policy=_policy(
            planning_depth=PlanningDepth.MEDIUM,
            evidence_strategy="decision_support",
        ),
        project_context_summary=None,
    )

    asyncio.run(DecompositionPlannerService().plan(context))

    assert context.running_state.comparison_candidates == []
    assert (
        "Comparison candidates are not explicit enough for structured comparison."
        in context.running_state.information_gaps
    )
    assert "Project context is limited for recommendation grounding." in (
        context.running_state.information_gaps
    )


def test_supplemental_project_context_satisfies_project_grounding_gap() -> None:
    context = _context(
        query="Recommend the best next architecture improvement.",
        task_type=TaskType.RECOMMENDATION,
        policy=_policy(
            planning_depth=PlanningDepth.MEDIUM,
            evidence_strategy="decision_support",
        ),
        project_context_summary=None,
        supplemental_context=SupplementalContext(
            project_support=[
                ContextItem(
                    id="project-ctx-1",
                    source_type="project_profile",
                    summary="The project is implementing core components.",
                    priority=10,
                )
            ]
        ),
    )

    asyncio.run(DecompositionPlannerService().plan(context))

    assert "Project context is limited for recommendation grounding." not in (
        context.running_state.information_gaps
    )


def test_planning_depth_none_skips_explicit_planning() -> None:
    context = _context(
        task_type=TaskType.TOPIC_EXPLORATION,
        policy=_policy(planning_depth=PlanningDepth.NONE),
    )
    context.running_state.plan = ["existing"]
    context.running_state.sub_questions = ["existing"]
    context.running_state.comparison_candidates = ["existing"]
    context.running_state.initial_evidence_strategy = ["existing"]

    asyncio.run(DecompositionPlannerService().plan(context))

    state = context.running_state
    assert state.planning_depth == PlanningDepth.NONE
    assert state.plan == []
    assert state.sub_questions == []
    assert state.comparison_candidates == []
    assert state.initial_evidence_strategy == []
