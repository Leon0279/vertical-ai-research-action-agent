"""Contract for LLM adapter clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClientProtocol(Protocol):
    """定义大语言模型客户端的抽象交互契约。

Protocol for LLM interactions."""

    async def generate_text(self, prompt: str) -> str:
        """Return generated text for a prompt."""

