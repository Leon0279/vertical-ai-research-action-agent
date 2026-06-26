"""Contract for Tool Execution Layer coordination."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ToolExecutionLayerRequest, ToolExecutionLayerResult


@runtime_checkable
class ToolExecutionLayerServiceProtocol(Protocol):
    """Research Executor-facing Tool Execution Layer service interface."""

    async def execute(
        self,
        request: ToolExecutionLayerRequest,
    ) -> ToolExecutionLayerResult:
        """Execute one bounded Tool Execution Layer request."""
