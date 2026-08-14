"""Error type for the llms.txt docs search adapter."""


class LlmsTxtDocsSearchClientError(RuntimeError):
    """表示 llms.txt 文档搜索过程中的错误。

Raised when docs search configuration, retrieval, or parsing fails."""
