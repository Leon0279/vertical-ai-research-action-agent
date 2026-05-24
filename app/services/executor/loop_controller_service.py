"""Loop continuation policy skeleton."""

from app.domain.models import ExecutionState
from app.services.executor.execution_guardrails import ExecutionGuardrails


class LoopControllerService:
    """Simple loop controller bounded by static guardrails."""

    def __init__(self, guardrails: ExecutionGuardrails | None = None) -> None:
        self._guardrails = guardrails or ExecutionGuardrails()

    async def should_continue(self, state: ExecutionState, iteration: int) -> bool:
        _ = state
        return iteration < self._guardrails.max_iterations
