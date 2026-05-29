"""Memory distillation skeleton."""

from app.domain.enums.memory_type import MemoryType
from app.domain.models import ExecutionContext, MemoryCandidate
from app.services.memory.contracts.memory_distiller_protocol import MemoryDistillerProtocol


class MemoryDistillerService(MemoryDistillerProtocol):
    """Extract durable memory candidates from current run."""

    async def distill(self, context: ExecutionContext) -> list[MemoryCandidate]:
        state = context.running_state
        candidates: list[MemoryCandidate] = []

        if state.final_recommendation:
            candidates.append(
                MemoryCandidate(
                    memory_type=MemoryType.DECISION,
                    summary=state.final_recommendation,
                    payload={
                        "task_type": state.task_type,
                        "project_scope_id": state.project_scope_id,
                    },
                    confidence=self._confidence_to_score(state.confidence),
                )
            )

        return candidates

    def _confidence_to_score(self, confidence: str | None) -> float | None:
        if confidence is None:
            return None
        return {
            "low": 0.2,
            "medium": 0.5,
            "high": 0.8,
        }.get(confidence.lower())
