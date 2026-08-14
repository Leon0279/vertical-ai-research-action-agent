"""Errors for the arXiv paper search adapter."""


class ArxivPaperSearchClientError(RuntimeError):
    """表示arXiv论文搜索客户端执行过程中发生的错误。

Raised when arXiv paper search fails or returns invalid data."""
