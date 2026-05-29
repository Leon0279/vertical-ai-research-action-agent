"""Loop continuation policy skeleton."""

from app.domain.models import ExecutionContext
from app.services.executor.contracts.loop_controller_protocol import LoopControllerProtocol
from app.services.executor.execution_guardrails import ExecutionGuardrails


class LoopControllerService(LoopControllerProtocol):
    """Simple loop controller bounded by static guardrails."""

    def __init__(self, guardrails: ExecutionGuardrails | None = None) -> None:
        self._guardrails = guardrails or ExecutionGuardrails()

    async def should_continue(self, context: ExecutionContext, iteration: int) -> bool:
        _ = context
        return iteration < self._guardrails.max_iterations
