"""Top-level fixed workflow pipeline."""

from __future__ import annotations

from app.domain.models import ExecutionContext, MemoryCandidate, RequestContext, StructuredOutput
from app.orchestration.pipeline_dependencies import PipelineDependencies, build_default_dependencies


class ResearchActionPipeline:
    """Fixed outer workflow with stage-by-stage execution."""

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
        await self._dependencies.research_executor.execute(context)

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
        await self._dependencies.memory_persistence.persist(candidates)

    async def _output(self, context: ExecutionContext) -> StructuredOutput:
        """Update session continuity and build final response."""

        context.runtime_context.stage_history.append("output")
        await self._dependencies.session_continuity_manager.update(context)
        return await self._dependencies.response_assembler.assemble(context)


def build_default_pipeline() -> ResearchActionPipeline:
    """Construct pipeline with all default stub dependencies."""

    return ResearchActionPipeline(dependencies=build_default_dependencies())
