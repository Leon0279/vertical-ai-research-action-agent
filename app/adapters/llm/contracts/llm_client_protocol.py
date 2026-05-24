"""Contract for LLM adapter clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for LLM interactions."""

    async def generate_text(self, prompt: str) -> str:
        """Return generated text for a prompt."""

