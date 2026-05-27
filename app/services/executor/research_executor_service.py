"""Research execution loop skeleton."""

from __future__ import annotations

from app.domain.models import ExecutionState, IntermediateFinding
from app.services.executor.contracts.research_executor_protocol import ResearchExecutorProtocol
from app.services.evidence.contracts.evidence_processor_protocol import EvidenceProcessorProtocol
from app.services.executor.contracts.loop_controller_protocol import LoopControllerProtocol
from app.services.retrieval.contracts.retrieval_service_protocol import RetrievalServiceProtocol


class ResearchExecutorService(ResearchExecutorProtocol):
    """Iterative evidence-driven execution loop with stub behavior."""

    def __init__(
        self,
        retrieval_service: RetrievalServiceProtocol,
        evidence_processor: EvidenceProcessorProtocol,
        loop_controller: LoopControllerProtocol,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._evidence_processor = evidence_processor
        self._loop_controller = loop_controller

    async def execute(self, state: ExecutionState) -> None:
        iteration = 0
        collected = []

        while await self._loop_controller.should_continue(state=state, iteration=iteration):
            iteration += 1
            batch = await self._retrieval_service.retrieve(query=state.original_query, limit=5)
            collected.extend(batch)
            if not batch:
                break

        normalized = await self._evidence_processor.normalize(collected)
        state.retrieved_evidence = normalized
        state.evidence_summary = await self._evidence_processor.summarize(normalized)
        state.intermediate_findings = [
            IntermediateFinding(
                statement="Research loop completed with stubbed retrieval backend.",
                rationale="No real external retrieval is enabled in Phase 1.",
                confidence=0.2,
            )
        ]
