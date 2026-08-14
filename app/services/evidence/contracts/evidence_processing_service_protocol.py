"""Contract for the new Evidence Processing service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import EvidenceProcessingRequest, EvidenceProcessingResult


@runtime_checkable
class EvidenceProcessingServiceProtocol(Protocol):
    """定义证据处理服务的抽象交互契约。

Converts Tool Execution Layer outputs into processed evidence units."""

    async def process(
        self,
        request: EvidenceProcessingRequest,
    ) -> EvidenceProcessingResult:
        """Process one current-round candidate material set."""
