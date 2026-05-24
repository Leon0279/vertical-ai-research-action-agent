"""No-op tool executor."""

from __future__ import annotations

from typing import Any


class StubToolExecutor:
    """Stub executor that reports no external execution."""

    async def execute(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"tool_name": tool_name, "payload": payload, "status": "stubbed"}
