"""Contract for embedding generation clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import EmbeddingResult


@runtime_checkable
class EmbeddingClientProtocol(Protocol):
    """Protocol for text embedding generation adapters."""

    async def embed_text(self, text: str) -> EmbeddingResult:
        """Generate an embedding for one text."""

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for a batch of texts."""
