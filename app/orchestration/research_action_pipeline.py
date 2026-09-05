"""Top-level fixed workflow pipeline."""

from __future__ import annotations

import logging
from time import perf_counter
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.common.observability import (
    bind_trace_id,
    exception_diagnostic_fields,
    reset_trace_id,
)
from app.domain.models import (
    ExecutionContext,
    MemoryCandidate,
    MemoryPersistenceResult,
    RequestContext,
    ResearchStageInput,
    ResearchStageResult,
    SourceReference,
    StructuredOutput,
)
from app.orchestration.pipeline_dependencies import PipelineDependencies, build_default_dependencies

T = TypeVar("T")
logger = logging.getLogger(__name__)


class ResearchActionPipeline:
    """按固定阶段驱动研究与行动工作流。

Fixed outer workflow with stage-by-stage execution."""

    def __init__(self, dependencies: PipelineDependencies) -> None:
        self._dependencies = dependencies

    async def run(self, request: RequestContext) -> StructuredOutput:
        """执行固定外层研究工作流，并返回面向调用方的最终结构化响应。

        Args:
            request (RequestContext): 外部传入的请求上下文，包含用户输入、身份与会话边界、能力声明和运行时约束。

        Returns:
            StructuredOutput: 经请求接入、规划、研究、结论、记忆写回和输出组装后得到的用户可读结果。
        """
        started_at = perf_counter()
        context: ExecutionContext | None = None
        trace_token = None
        try:
            context = await self._request_intake(request)
            trace_token = bind_trace_id(context.runtime_context.request_id)
            logger.info(
                "Agent run started.",
                extra={"event": "agent_run_started"},
            )
            await self._run_pipeline_stage(
                context,
                "task_interpretation",
                self._task_interpretation,
            )
            await self._run_pipeline_stage(
                context,
                "context_memory_load",
                self._context_memory_load,
            )
            await self._run_pipeline_stage(
                context,
                "workflow_routing",
                self._workflow_routing,
            )
            await self._run_pipeline_stage(context, "planning", self._planning)
            await self._run_pipeline_stage(context, "research", self._research)
            await self._run_pipeline_stage(context, "conclusion", self._conclusion)
            await self._run_pipeline_stage(
                context,
                "memory_writeback",
                self._memory_writeback,
            )
            output = await self._run_pipeline_stage(context, "output", self._output)
            logger.info(
                "Agent run completed.",
                extra={
                    "event": "agent_run_completed",
                    "duration_ms": _elapsed_ms(started_at),
                    "research_status": context.running_state.research_status,
                    "research_iteration_count": (
                        context.running_state.research_iteration_count
                    ),
                    "citation_count": len(output.citations),
                },
            )
            return output
        except Exception as error:
            extra = {
                "event": "agent_run_failed",
                "duration_ms": _elapsed_ms(started_at),
                **exception_diagnostic_fields(error),
            }
            if context is not None:
                extra["research_status"] = context.running_state.research_status
                extra["research_iteration_count"] = (
                    context.running_state.research_iteration_count
                )
            logger.exception("Agent run failed.", extra=extra)
            raise
        finally:
            if trace_token is not None:
                reset_trace_id(trace_token)

    async def _run_pipeline_stage(
        self,
        context: ExecutionContext,
        stage_name: str,
        operation: Callable[[ExecutionContext], Awaitable[T]],
    ) -> T:
        """Run one pipeline stage with consistent trace-correlated lifecycle logs."""

        started_at = perf_counter()
        logger.info(
            "Pipeline stage started.",
            extra={
                "event": "pipeline_stage_started",
                "stage_name": stage_name,
                "stage_status": "started",
            },
        )
        try:
            result = await operation(context)
        except Exception as error:
            logger.exception(
                "Pipeline stage failed.",
                extra={
                    "event": "pipeline_stage_failed",
                    "stage_name": stage_name,
                    "stage_status": "failed",
                    "duration_ms": _elapsed_ms(started_at),
                    **exception_diagnostic_fields(error),
                },
            )
            raise
        logger.info(
            "Pipeline stage completed.",
            extra={
                "event": "pipeline_stage_completed",
                "stage_name": stage_name,
                "stage_status": "completed",
                "duration_ms": _elapsed_ms(started_at),
                **self._stage_summary(context, stage_name, result),
            },
        )
        return result

    def _stage_summary(
        self,
        context: ExecutionContext,
        stage_name: str,
        result: object,
    ) -> dict[str, Any]:
        """Return allow-listed structural diagnostics without stage payload content."""

        state = context.running_state
        supplemental = context.supplemental_context
        if stage_name == "task_interpretation":
            return {
                "task_type": state.task_type,
                "constraint_count": len(state.constraints),
            }
        if stage_name == "context_memory_load":
            return {
                "session_support_count": len(supplemental.session_support),
                "project_support_count": len(supplemental.project_support),
                "decision_support_count": len(supplemental.decision_support),
                "action_support_count": len(supplemental.action_support),
                "policy_support_count": len(supplemental.policy_support),
                "research_support_count": len(supplemental.research_support),
            }
        if stage_name == "workflow_routing":
            policy = state.execution_policy
            return {
                "workflow_pattern": state.workflow_pattern,
                "planning_depth": policy.planning_depth if policy else None,
                "evidence_strategy": policy.evidence_strategy if policy else None,
                "memory_writeback_focus": (
                    list(policy.memory_writeback_focus) if policy else []
                ),
            }
        if stage_name == "planning":
            return {
                "planning_depth": state.planning_depth,
                "plan_step_count": len(state.plan),
                "sub_question_count": len(state.sub_questions),
                "comparison_candidate_count": len(state.comparison_candidates),
                "information_gap_count": len(state.information_gaps),
                "initial_evidence_strategy_count": len(
                    state.initial_evidence_strategy
                ),
            }
        if stage_name == "research":
            return {
                "research_status": state.research_status,
                "research_iteration_count": state.research_iteration_count,
                "citation_count": len(state.retrieved_evidence_refs),
            }
        if stage_name == "conclusion":
            return {
                "answer_present": bool(state.final_answer),
                "summary_present": bool(state.final_summary),
                "recommendation_present": bool(state.final_recommendation),
                "action_item_count": len(state.action_items),
                "caveat_count": len(state.caveats),
                "confidence": state.confidence,
                "citation_count": len(state.retrieved_evidence_refs),
            }
        if stage_name == "memory_writeback" and isinstance(
            result,
            MemoryPersistenceResult,
        ):
            return {
                "written_count": result.written_count,
                "no_write_count": result.no_write_count,
                "failed_count": result.failed_count,
            }
        if stage_name == "output" and isinstance(result, StructuredOutput):
            return {
                "citation_count": len(result.citations),
                "action_item_count": len(result.action_items),
                "caveat_count": len(result.caveats),
                "confidence": result.confidence,
            }
        return {}

    async def _request_intake(self, request: RequestContext) -> ExecutionContext:
        """Initialize execution context from the incoming request."""

        return await self._dependencies.request_intake.intake(request)

    async def _task_interpretation(self, context: ExecutionContext) -> None:
        """Infer task intent fields."""

        context.runtime_context.stage_history.append("task_interpretation")
        await self._dependencies.task_interpreter.interpret(context)

    async def _context_memory_load(self, context: ExecutionContext) -> None:
        """Load relevant short-term and long-term memory."""

        context.runtime_context.stage_history.append("context_memory_load")
        await self._dependencies.context_memory_loader.load(context)

    async def _workflow_routing(self, context: ExecutionContext) -> None:
        """Select workflow pattern for current task."""

        context.runtime_context.stage_history.append("workflow_routing")
        await self._dependencies.workflow_router.route(context)

    async def _planning(self, context: ExecutionContext) -> None:
        """Generate planning artifacts when needed."""

        context.runtime_context.stage_history.append("planning")
        await self._dependencies.decomposition_planner.plan(context)

    async def _research(self, context: ExecutionContext) -> None:
        """Run evidence-driven execution loop."""

        context.runtime_context.stage_history.append("research")
        stage_input = self._build_research_stage_input(context)
        try:
            stage_result = await self._dependencies.research_executor.execute(stage_input)
        except Exception as error:
            logger.exception(
                "Research stage execution failed.",
                extra={
                    "event": "research_stage_failed",
                    "trace_id": context.runtime_context.request_id,
                    **exception_diagnostic_fields(error),
                },
            )
            stage_result = ResearchStageResult(
                research_status="failed",
                open_questions=[
                    "研究阶段在生成或处理证据时遇到运行错误，未能形成可靠材料。"
                ],
                error_info="Research stage execution failed.",
            )
        self._apply_research_stage_result(context, stage_result)

    def _build_research_stage_input(self, context: ExecutionContext) -> ResearchStageInput:
        """Project the full execution context into the research stage input."""

        state = context.running_state
        supplemental_context = context.supplemental_context
        runtime_context = context.runtime_context

        return ResearchStageInput(
            original_query=state.original_query,
            task_type=state.task_type,
            user_goal=state.user_goal,
            task_framing=state.task_framing,
            constraints=state.constraints,
            project_scope_id=state.project_scope_id,
            owner_user_id=runtime_context.user_id,
            project_context_summary=state.project_context_summary,
            plan=state.plan,
            sub_questions=state.sub_questions,
            comparison_candidates=state.comparison_candidates,
            information_gaps=state.information_gaps,
            initial_evidence_strategy=state.initial_evidence_strategy,
            active_decision_summary=state.active_decision_summary,
            current_action_status=state.current_action_status,
            current_bottleneck_summary=state.current_bottleneck_summary,
            existing_intermediate_findings=state.intermediate_findings,
            research_support=supplemental_context.research_support,
            decision_support=supplemental_context.decision_support,
            action_support=supplemental_context.action_support,
            available_families=runtime_context.available_families,
            latency_budget_ms=runtime_context.latency_budget_ms,
            iteration_budget=runtime_context.iteration_budget,
            scope_restrictions=runtime_context.scope_restrictions,
        )

    def _apply_research_stage_result(
        self,
        context: ExecutionContext,
        result: ResearchStageResult,
    ) -> None:
        """Write research stage output back into the execution context."""

        state = context.running_state
        state.retrieved_evidence_refs = self._append_unique_source_references(
            state.retrieved_evidence_refs,
            result.retrieved_evidence_refs,
        )
        state.intermediate_findings = self._append_unique(
            state.intermediate_findings,
            result.intermediate_findings,
        )
        state.open_questions = self._append_unique(
            state.open_questions,
            result.open_questions,
        )
        state.research_status = result.research_status
        state.research_iteration_count = result.executed_iteration_count

        if result.evidence_summary is not None:
            state.evidence_summary = result.evidence_summary
        if result.error_info:
            logger.warning(
                "Research stage returned an error result.",
                extra={
                    "research_status": result.research_status,
                    "research_error_info": result.error_info,
                    "trace_id": context.runtime_context.request_id,
                },
            )

    @staticmethod
    def _append_unique(existing: list[T], additions: list[T]) -> list[T]:
        """Append values in order without duplicating existing entries."""

        merged = list(existing)
        for item in additions:
            if item not in merged:
                merged.append(item)
        return merged

    @classmethod
    def _append_unique_source_references(
        cls,
        existing: list[SourceReference],
        additions: list[SourceReference],
    ) -> list[SourceReference]:
        """Append SourceReference values using stable source identity keys."""

        merged = list(existing)
        seen = {item.deduplication_key() for item in merged}
        for item in additions:
            key = item.deduplication_key()
            if key not in seen:
                merged.append(item)
                seen.add(key)
        return merged

    async def _conclusion(self, context: ExecutionContext) -> None:
        """Generate structured conclusion."""

        context.runtime_context.stage_history.append("conclusion")
        await self._dependencies.conclusion_generator.generate(context)

    async def _memory_writeback(
        self,
        context: ExecutionContext,
    ) -> MemoryPersistenceResult:
        """Distill and persist long-term memory candidates."""

        context.runtime_context.stage_history.append("memory_writeback")
        started_at = perf_counter()
        candidates: list[MemoryCandidate] = []
        try:
            candidates = await self._dependencies.memory_distiller.distill(context)
            result = await self._dependencies.memory_persistence.persist(
                context,
                candidates,
            )
        except Exception as error:
            logger.exception(
                "Memory write-back failed without blocking the response.",
                extra={
                    "event": "memory_writeback_failed",
                    "duration_ms": _elapsed_ms(started_at),
                    "candidate_count": len(candidates),
                    **exception_diagnostic_fields(error),
                },
            )
            return MemoryPersistenceResult(failed_count=len(candidates))

        logger.log(
            logging.WARNING if result.failed_count else logging.INFO,
            "Memory write-back completed.",
            extra={
                "event": "memory_writeback_completed",
                "duration_ms": _elapsed_ms(started_at),
                "candidate_count": len(candidates),
                "candidate_memory_types": [
                    candidate.memory_type for candidate in candidates
                ],
                "stable_candidate_count": sum(
                    candidate.stability == "stable" for candidate in candidates
                ),
                "tentative_candidate_count": sum(
                    candidate.stability == "tentative" for candidate in candidates
                ),
                "source_reference_count": sum(
                    len(candidate.source_references) for candidate in candidates
                ),
                "written_count": result.written_count,
                "no_write_count": result.no_write_count,
                "failed_count": result.failed_count,
                "memory_persistence_items": [
                    {
                        "memory_type": item.memory_type,
                        "action": item.action,
                        "status": item.status,
                        "written_record_id": item.written_record_id,
                        "no_write_reason": item.no_write_reason,
                        "error_info": item.error_info,
                    }
                    for item in result.items
                ],
            },
        )
        return result

    async def _output(self, context: ExecutionContext) -> StructuredOutput:
        """Update session continuity and build final response."""

        context.runtime_context.stage_history.append("output")
        await self._dependencies.session_continuity_manager.update(context)
        return await self._dependencies.response_assembler.assemble(context)


def build_default_pipeline() -> ResearchActionPipeline:
    """Construct pipeline with all default stub dependencies."""

    return ResearchActionPipeline(dependencies=build_default_dependencies())


def _elapsed_ms(started_at: float) -> int:
    """Return a non-negative elapsed duration for structured logs."""

    return max(0, round((perf_counter() - started_at) * 1000))
