"""Contract for family selection in the tool execution layer."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import FamilySelectionRequest, FamilySelectionResult


@runtime_checkable
class FamilySelectionServiceProtocol(Protocol):
    """定义检索族选择服务的抽象交互契约。

Runtime-facing interface for selecting a retrieval family."""

    async def select_family(self, request: FamilySelectionRequest) -> FamilySelectionResult:
        """根据检索意图、范围和约束选择下一次调用的 retrieval family。

        Args:
            request (FamilySelectionRequest): 包含目标问题、证据需求、允许或偏好的 family 与 action mode 的选择请求。

        Returns:
            FamilySelectionResult: family 候选排序、最终选择、选择理由和无匹配时的状态信息。
        """
