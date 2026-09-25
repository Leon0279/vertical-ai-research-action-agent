"""Decomposition planner service tests."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from app.domain.enums import FamilyName, TaskType, WorkflowPattern
from app.domain.models import (
    ContextItem,
    ExecutionContext,
    RunningState,
    RuntimeContext,
    SupplementalContext,
)
from app.services.planner.decomposition_planner_service import (
    DecompositionPlannerService,
)


class FakeLLMClient:
    """Return one configured JSON object or raise one configured error."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or {}
        self.error = error
        self.prompts: list[str] = []

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return dict(self.payload)

    async def generate_text(self, prompt: str) -> str:
        raise AssertionError(f"Planner must not call generate_text: {prompt[:20]}")


def _planning_payload(
    *,
    plan: list[str] | None = None,
    sub_questions: list[str] | None = None,
    comparison_candidates: list[str] | None = None,
    initial_evidence_strategy: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "plan": plan if plan is not None else ["明确比较标准。"],
        "sub_questions": (
            sub_questions
            if sub_questions is not None
            else ["两种方案在当前约束下各有什么取舍？"]
        ),
        "comparison_candidates": (
            comparison_candidates
            if comparison_candidates is not None
            else ["Redis", "Postgres"]
        ),
        "initial_evidence_strategy": (
            initial_evidence_strategy
            if initial_evidence_strategy is not None
            else ["优先收集相同条件下的对比证据。"]
        ),
    }


def _context(
    *,
    query: str = "Compare Redis vs Postgres for session memory",
    task_type: TaskType | None = TaskType.COMPARISON,
    information_gaps: list[str] | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(
            original_query=query,
            task_type=task_type.value if task_type else None,
            user_goal=query,
            task_framing="为当前项目选择 session memory 方案",
            constraints=["单人开发", "需要低运维成本"],
            project_scope_id="project-1",
            project_context_summary="项目处于 MVP 阶段。",
            current_bottleneck_summary="缺少可量化的存储基线。",
            active_decision_summary="暂不引入复杂分布式组件。",
            current_action_status="正在验证 session continuity。",
            workflow_pattern=WorkflowPattern.COMPARISON,
            information_gaps=list(information_gaps or []),
            open_questions=["峰值流量下的成本是多少？"],
        ),
        supplemental_context=SupplementalContext(
            session_support=[
                ContextItem(
                    id="session-1",
                    source_type="session_memory",
                    summary="上一轮决定先比较读写延迟。",
                    priority=8,
                )
            ],
            project_support=[
                ContextItem(
                    id="project-1",
                    source_type="project_profile",
                    summary="当前项目优先交付 MVP。",
                    priority=10,
                )
            ],
            decision_support=[
                ContextItem(
                    id="decision-1",
                    source_type="decision_memory",
                    summary="已决定避免过早拆分微服务。",
                    priority=9,
                )
            ],
            action_support=[
                ContextItem(
                    id="action-1",
                    source_type="action_memory",
                    summary="Redis 原型已经完成。",
                    priority=7,
                )
            ],
            policy_support=[
                ContextItem(
                    id="policy-1",
                    source_type="research_policy",
                    summary="优先使用可核验资料。",
                    priority=6,
                )
            ],
            research_support=[
                ContextItem(
                    id="research-1",
                    source_type="research_memory",
                    summary="已有一份 session store 对比摘要。",
                    priority=8,
                )
            ],
        ),
        runtime_context=RuntimeContext(
            request_id="run-1",
            user_id="user-1",
            session_id="session-1",
            latency_budget_ms=5_000,
            iteration_budget=3,
            scope_restrictions=["仅评估当前项目可采用的方案"],
            available_families=[
                FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                FamilyName.DOCS_SEARCH,
            ],
        ),
    )


def test_llm_planning_updates_all_owned_fields_once() -> None:
    context = _context(information_gaps=["保留的旧缺口"])
    llm = FakeLLMClient(_planning_payload())

    asyncio.run(DecompositionPlannerService(llm).plan(context))

    state = context.running_state
    assert len(llm.prompts) == 1
    assert state.plan == ["明确比较标准。"]
    assert state.sub_questions == ["两种方案在当前约束下各有什么取舍？"]
    assert state.comparison_candidates == ["Redis", "Postgres"]
    assert state.initial_evidence_strategy == ["优先收集相同条件下的对比证据。"]
    assert state.information_gaps == ["保留的旧缺口"]


def test_llm_can_generate_rich_artifacts_for_topic_exploration() -> None:
    context = _context(
        query="解释一个跨存储、检索和评测的复杂 Agent 架构",
        task_type=TaskType.TOPIC_EXPLORATION,
    )
    llm = FakeLLMClient(
        _planning_payload(
            plan=["划分架构边界。", "分别分析存储、检索和评测。"],
            sub_questions=["各模块如何协作？"],
            comparison_candidates=[],
            initial_evidence_strategy=["分别收集三个模块的设计证据。"],
        )
    )

    asyncio.run(DecompositionPlannerService(llm).plan(context))

    assert len(context.running_state.plan) == 2
    assert context.running_state.sub_questions == ["各模块如何协作？"]


def test_empty_artifacts_select_direct_path_and_preserve_information_gaps() -> None:
    context = _context(information_gaps=["既有缺口"])
    context.running_state.plan = ["旧计划"]
    context.running_state.sub_questions = ["旧问题"]
    context.running_state.comparison_candidates = ["Redis"]
    context.running_state.initial_evidence_strategy = ["旧策略"]
    llm = FakeLLMClient(
        _planning_payload(
            plan=[],
            sub_questions=[],
            comparison_candidates=[],
            initial_evidence_strategy=[],
        )
    )

    asyncio.run(DecompositionPlannerService(llm).plan(context))

    state = context.running_state
    assert state.plan == []
    assert state.sub_questions == []
    assert state.comparison_candidates == []
    assert state.initial_evidence_strategy == []
    assert state.information_gaps == ["既有缺口"]


def test_llm_lists_are_trimmed_deduplicated_and_bounded() -> None:
    long_item = "x" * 600
    plan = ["  第一步  ", "第一步", " ", long_item]
    plan.extend(f"步骤 {index}" for index in range(10))
    context = _context()
    llm = FakeLLMClient(
        _planning_payload(
            plan=plan,
            comparison_candidates=[],
        )
    )

    asyncio.run(DecompositionPlannerService(llm).plan(context))

    assert context.running_state.plan[0] == "第一步"
    assert len(context.running_state.plan) == 8
    assert max(map(len, context.running_state.plan)) == 500


def test_prompt_is_self_contained_and_includes_distilled_context() -> None:
    context = _context()
    llm = FakeLLMClient(_planning_payload())

    asyncio.run(DecompositionPlannerService(llm).plan(context))

    prompt = llm.prompts[0]
    assert "无状态" in prompt
    assert '"request_context"' in prompt
    assert '"project_state"' in prompt
    assert '"distilled_supporting_materials"' in prompt
    assert '"runtime_limits"' in prompt
    assert "上一轮决定先比较读写延迟" in prompt
    assert "优先使用可核验资料" in prompt
    assert '"available_families"' in prompt
    assert "research_knowledge_recall" in prompt
    assert "四个列表可以全部返回空列表" in prompt
    assert "planning_depth" not in prompt
    assert "不要输出 information_gaps" in prompt
    assert "不是搜索词、具体工具参数或执行命令" in prompt
    assert "ExecutionContext" not in prompt
    assert "RunningState" not in prompt
    assert "ContextItem" not in prompt


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {**_planning_payload(), "unexpected": True},
        {**_planning_payload(), "planning_depth": "MEDIUM"},
        {
            key: value
            for key, value in _planning_payload().items()
            if key != "plan"
        },
        _planning_payload(comparison_candidates=["MongoDB"]),
    ],
)
def test_invalid_llm_output_uses_fallback_and_preserves_information_gaps(
    invalid_payload: dict[str, Any],
) -> None:
    context = _context(information_gaps=["不能修改"])
    llm = FakeLLMClient(invalid_payload)

    asyncio.run(DecompositionPlannerService(llm).plan(context))

    state = context.running_state
    assert len(llm.prompts) == 1
    assert state.comparison_candidates == ["Redis", "Postgres"]
    assert state.information_gaps == ["不能修改"]
    assert all(not item.startswith("Objective:") for item in state.plan)


def test_llm_failure_uses_fallback_and_logs_reason(caplog: pytest.LogCaptureFixture) -> None:
    context = _context(information_gaps=["保持不变"])
    llm = FakeLLMClient(error=RuntimeError("provider unavailable"))

    with caplog.at_level(logging.INFO):
        asyncio.run(DecompositionPlannerService(llm).plan(context))

    assert context.running_state.information_gaps == ["保持不变"]
    completed = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "planning_completed"
    )
    assert completed.planning_source == "deterministic_fallback"
    assert completed.fallback_reason == "llm_call_failed"


@pytest.mark.parametrize(
    ("task_type", "expected_text"),
    [
        (TaskType.TOPIC_EXPLORATION, "background knowledge"),
        (TaskType.COMPARISON, "tradeoffs"),
        (TaskType.RECOMMENDATION, "decision-support"),
        (TaskType.ACTION_PLANNING, "dependencies"),
        (TaskType.TRACKING, "fresh status"),
    ],
)
def test_fallback_covers_each_task_type(
    task_type: TaskType,
    expected_text: str,
) -> None:
    context = _context(
        query="Explain the next project step.",
        task_type=task_type,
        information_gaps=["已有信息缺口"],
    )

    asyncio.run(DecompositionPlannerService(FakeLLMClient({})).plan(context))

    state = context.running_state
    assert any(
        expected_text in item
        for item in [*state.plan, *state.sub_questions, *state.initial_evidence_strategy]
    )
    assert state.information_gaps == ["已有信息缺口"]


def test_successful_llm_path_logs_source(caplog: pytest.LogCaptureFixture) -> None:
    context = _context()

    with caplog.at_level(logging.INFO):
        asyncio.run(
            DecompositionPlannerService(FakeLLMClient(_planning_payload())).plan(
                context
            )
        )

    completed = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "planning_completed"
    )
    assert completed.planning_source == "llm"
    assert completed.fallback_reason is None
    assert not hasattr(completed, "planning_depth")
