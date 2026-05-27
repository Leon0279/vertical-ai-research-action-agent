"""Memory distillation skeleton."""

from app.domain.enums.memory_type import MemoryType
from app.domain.models import ExecutionState, MemoryCandidate
from app.services.memory.contracts.memory_distiller_protocol import MemoryDistillerProtocol


class MemoryDistillerService(MemoryDistillerProtocol):
    """Extract durable memory candidates from current run."""

    async def distill(self, state: ExecutionState) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []

        if state.final_recommendation:
            candidates.append(
                MemoryCandidate(
                    memory_type=MemoryType.DECISION,
                    summary=state.final_recommendation.recommendation,
                    payload={
                        "rationale": state.final_recommendation.rationale,
                        "task_type": state.task_type.value if state.task_type else None,
                    },
                    confidence=state.confidence,
                )
            )

        state.memory_candidates = candidates
        return candidates
