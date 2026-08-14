"""Contract for provider-backed web content fetch clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import WebContentFetchRequest, WebContentFetchResponse


@runtime_checkable
class WebContentFetchClientProtocol(Protocol):
    """定义网页内容获取客户端的抽象交互契约。

Provider-neutral interface for normalized web content fetch adapters."""

    async def fetch_content(
        self,
        request: WebContentFetchRequest,
    ) -> WebContentFetchResponse:
        """抓取一个或多个 URL 的正文并归一化为内容获取响应。

        Args:
            request (WebContentFetchRequest): URL 列表、抽取深度和内容格式等正文抓取请求。

        Returns:
            WebContentFetchResponse: 成功与失败条目均已归一化的网页内容获取响应。
        """
