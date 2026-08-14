"""Errors for the Tavily web search adapter."""


class TavilyWebSearchClientError(RuntimeError):
    """表示Tavily网页搜索客户端执行过程中发生的错误。

Raised when Tavily web search fails or returns invalid data."""
