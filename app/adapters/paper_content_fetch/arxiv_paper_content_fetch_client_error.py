"""Error type for the arXiv paper content fetch adapter."""


class ArxivPaperContentFetchClientError(RuntimeError):
    """表示arXiv论文内容获取客户端执行过程中发生的错误。

Raised when arXiv PDF content fetch configuration or inputs are invalid."""
