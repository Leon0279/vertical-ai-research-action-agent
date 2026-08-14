"""Contract for LLM adapter clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClientProtocol(Protocol):
    """定义大语言模型客户端的抽象交互契约。

Protocol for LLM interactions."""

    async def generate_text(self, prompt: str) -> str:
        """基于完整 prompt 生成文本响应。

        Args:
            prompt (str): 已由调用方构造好的完整提示词；adapter 不应假设存在额外会话上下文。

        Returns:
            str: LLM 返回的原始生成文本，具体 JSON 或自然语言解析由上层 service 负责。
        """
