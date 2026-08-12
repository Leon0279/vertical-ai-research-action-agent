"""Memory distillation skeleton."""

from app.domain.enums.memory_type import MemoryType
from app.domain.models import ExecutionContext, MemoryCandidate
from app.services.memory.contracts.memory_distiller_protocol import MemoryDistillerProtocol


class MemoryDistillerService(MemoryDistillerProtocol):
    """从当前 run 的稳定输出中提取长期 memory candidate。"""

    async def distill(self, context: ExecutionContext) -> list[MemoryCandidate]:
        state = context.running_state
        candidates: list[MemoryCandidate] = []

        if state.final_recommendation:
            candidates.append(
                MemoryCandidate(
                    memory_type=MemoryType.DECISION,
                    semantic_type="stable_decision",
                    candidate_source="run_output",
                    summary=state.final_recommendation,
                    payload={
                        "task_type": state.task_type,
                    },
                    confidence=self._confidence_to_score(state.confidence),
                    stability=self._stability_from_state(context),
                    project_scope_id=state.project_scope_id,
                    source_references=list(state.retrieved_evidence_refs),
                    derived_from_run_id=context.runtime_context.request_id,
                    derived_from_session_id=context.runtime_context.session_id,
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

    def _stability_from_state(self, context: ExecutionContext) -> str:
        """Return the conservative persistence stability for the current recommendation."""

        state = context.running_state
        if state.confidence and state.confidence.lower() == "high":
            if not state.caveats and not state.open_questions:
                return "stable"
        return "tentative"
