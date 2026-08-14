"""Contract for family selection in the tool execution layer."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import FamilySelectionRequest, FamilySelectionResult


@runtime_checkable
class FamilySelectionServiceProtocol(Protocol):
    """定义检索族选择服务的抽象交互契约。

Runtime-facing interface for selecting a retrieval family."""

    async def select_family(self, request: FamilySelectionRequest) -> FamilySelectionResult:
        """Choose a family for downstream family service invocation."""
