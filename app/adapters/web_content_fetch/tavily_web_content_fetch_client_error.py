"""Errors for the Tavily web content fetch adapter."""


class TavilyWebContentFetchClientError(RuntimeError):
    """表示Tavily网页内容获取客户端执行过程中发生的错误。

Raised when Tavily Extract fails or returns invalid data."""
