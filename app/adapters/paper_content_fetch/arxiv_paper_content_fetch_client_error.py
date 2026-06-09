"""Error type for the arXiv paper content fetch adapter."""


class ArxivPaperContentFetchClientError(RuntimeError):
    """Raised when arXiv PDF content fetch configuration or inputs are invalid."""
