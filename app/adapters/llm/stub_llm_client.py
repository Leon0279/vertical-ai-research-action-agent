"""No-op LLM adapter used in Phase 1."""

from typing import Any

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol


class StubLLMClient(LLMClientProtocol):
    """提供避免真实外部调用的大语言模型测试替身。

Stub client that avoids real external calls."""

    async def generate_text(self, prompt: str) -> str:
        return f"[stub-llm] {prompt[:80]}"

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        _ = prompt
        return {}
