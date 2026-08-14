"""Contract for embedding generation clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import EmbeddingResult


@runtime_checkable
class EmbeddingClientProtocol(Protocol):
    """定义嵌入客户端的抽象交互契约。

Protocol for text embedding generation adapters."""

    async def embed_text(self, text: str) -> EmbeddingResult:
        """为单段文本生成 embedding 向量。

        Args:
            text (str): 需要向量化的非空文本。

        Returns:
            EmbeddingResult: 对应文本索引、向量、模型与 provider token 用量的结构化结果。
        """

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        """为一批文本生成 embedding 向量。

        Args:
            texts (list[str]): 按输入顺序需要向量化的文本列表。

        Returns:
            list[EmbeddingResult]: 与输入文本一一对应的 embedding 结果列表，保留输入索引。
        """
