"""Contract for LLM adapter clients."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClientProtocol(Protocol):
    """定义大语言模型客户端的抽象交互契约。

Protocol for LLM interactions."""

    async def generate_text(self, prompt: str) -> str:
        """基于完整 prompt 生成文本响应。

        Args:
            prompt (str): 已由调用方构造好的完整提示词；adapter 不应假设存在额外会话上下文。

        Returns:
            str: LLM 返回的普通文本；需要 JSON object 时应调用 generate_json_object。
        """

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        """基于完整 prompt 生成并解析一个 JSON object。

        Args:
            prompt (str): 已由调用方构造好的完整提示词；adapter 不应假设存在额外会话上下文。

        Returns:
            dict[str, Any]: LLM 返回且已通过 JSON object 语法校验的字典；业务 schema 仍由上层 service 校验。
        """
