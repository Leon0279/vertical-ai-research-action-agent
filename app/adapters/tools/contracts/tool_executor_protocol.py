"""Contract for tool executors."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ToolExecutorProtocol(Protocol):
    """Protocol for external tool invocation."""

    async def execute(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call with serialized payload."""

