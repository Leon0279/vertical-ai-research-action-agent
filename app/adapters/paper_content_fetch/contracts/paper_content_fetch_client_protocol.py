"""Contract for provider-backed paper content fetch clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import PaperContentFetchRequest, PaperContentFetchResult


@runtime_checkable
class PaperContentFetchClientProtocol(Protocol):
    """定义论文内容获取客户端的抽象交互契约。

Provider-neutral interface for paper fulltext fetch adapters."""

    async def fetch_content(
        self,
        request: PaperContentFetchRequest,
    ) -> PaperContentFetchResult:
        """根据 typed 论文标识抓取并提取论文正文内容。

        Args:
            request (PaperContentFetchRequest): 包含 paper_id 与 paper_id_type 的论文内容获取请求。

        Returns:
            PaperContentFetchResult: 论文内容获取结果，包含提取正文、来源 URL、状态与错误信息。
        """
