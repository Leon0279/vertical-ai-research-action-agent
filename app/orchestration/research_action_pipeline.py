"""Top-level fixed workflow pipeline."""

from __future__ import annotations

import json
from typing import TypeVar

from app.domain.models import (
    ExecutionContext,
    MemoryCandidate,
    RequestContext,
    ResearchStageInput,
    ResearchStageResult,
    SourceReference,
    StructuredOutput,
)
from app.orchestration.pipeline_dependencies import PipelineDependencies, build_default_dependencies

T = TypeVar("T")


class ResearchActionPipeline:
    """按固定阶段驱动研究与行动工作流。

Fixed outer workflow with stage-by-stage execution."""

    def __init__(self, dependencies: PipelineDependencies) -> None:
        self._dependencies = dependencies

    async def run(self, request: RequestContext) -> StructuredOutput:
        context = await self._request_intake(request)
        await self._task_interpretation(context)
        await self._context_memory_load(context)
        await self._workflow_routing(context)
        await self._planning(context)
        await self._research(context)
        await self._conclusion(context)
        await self._memory_writeback(context)
        return await self._output(context)

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
        stage_result = await self._dependencies.research_executor.execute(stage_input)
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
            existing_intermediate_findings=state.intermediate_findings,
            research_support=supplemental_context.research_support,
            decision_support=supplemental_context.decision_support,
            action_support=supplemental_context.action_support,
            available_tools=runtime_context.available_tools,
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

        if result.evidence_summary is not None:
            state.evidence_summary = result.evidence_summary

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
        seen = {cls._source_reference_key(item) for item in merged}
        for item in additions:
            key = cls._source_reference_key(item)
            if key not in seen:
                merged.append(item)
                seen.add(key)
        return merged

    @staticmethod
    def _source_reference_key(source_reference: SourceReference) -> str:
        """Return a stable deduplication key for a SourceReference."""

        if source_reference.source_url:
            return f"url:{source_reference.source_url}"
        if source_reference.source_id:
            return (
                f"id:{source_reference.source_id_type or ''}:"
                f"{source_reference.source_id}"
            )
        if source_reference.citation_text:
            return f"citation:{source_reference.citation_text}"
        return "json:" + json.dumps(
            source_reference.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )

    async def _conclusion(self, context: ExecutionContext) -> None:
        """Generate structured conclusion."""

        context.runtime_context.stage_history.append("conclusion")
        await self._dependencies.conclusion_generator.generate(context)

    async def _memory_writeback(self, context: ExecutionContext) -> None:
        """Distill and persist long-term memory candidates."""

        context.runtime_context.stage_history.append("memory_writeback")
        candidates: list[MemoryCandidate] = await self._dependencies.memory_distiller.distill(
            context
        )
        await self._dependencies.memory_persistence.persist(context, candidates)

    async def _output(self, context: ExecutionContext) -> StructuredOutput:
        """Update session continuity and build final response."""

        context.runtime_context.stage_history.append("output")
        await self._dependencies.session_continuity_manager.update(context)
        return await self._dependencies.response_assembler.assemble(context)


def build_default_pipeline() -> ResearchActionPipeline:
    """Construct pipeline with all default stub dependencies."""

    return ResearchActionPipeline(dependencies=build_default_dependencies())
