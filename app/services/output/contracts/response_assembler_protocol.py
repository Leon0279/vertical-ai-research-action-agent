"""Contract for response assembler services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext, StructuredOutput


@runtime_checkable
class ResponseAssemblerProtocol(Protocol):
    """定义响应组装器的抽象交互契约。

Assembles final user-facing outputs."""

    async def assemble(self, context: ExecutionContext) -> StructuredOutput:
        """Create a final structured output."""
