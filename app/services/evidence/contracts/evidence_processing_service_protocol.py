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
        """处理当前轮次的候选材料，并生成可供后续研究使用的结构化证据。

        Args:
            request (EvidenceProcessingRequest): 包含检索候选材料、来源信息和处理上下文的证据处理请求。

        Returns:
            EvidenceProcessingResult: 处理后的证据单元、覆盖摘要、处理状态及可能的错误信息。
        """
