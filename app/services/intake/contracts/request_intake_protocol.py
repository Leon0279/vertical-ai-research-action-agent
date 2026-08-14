"""Contract for request intake services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext, RequestContext


@runtime_checkable
class RequestIntakeProtocol(Protocol):
    """定义请求接入的抽象交互契约。

Build the initial execution context from an incoming request."""

    async def intake(self, request: RequestContext) -> ExecutionContext:
        """Normalize an incoming request into the canonical execution context."""
