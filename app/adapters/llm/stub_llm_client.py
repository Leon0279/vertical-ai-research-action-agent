"""No-op LLM adapter used in Phase 1."""

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol


class StubLLMClient(LLMClientProtocol):
    """Stub client that avoids real external calls."""

    async def generate_text(self, prompt: str) -> str:
        return f"[stub-llm] {prompt[:80]}"
