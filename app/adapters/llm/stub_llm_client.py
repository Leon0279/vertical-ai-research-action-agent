"""No-op LLM adapter used in Phase 1."""


class StubLLMClient:
    """Stub client that avoids real external calls."""

    async def generate_text(self, prompt: str) -> str:
        return f"[stub-llm] {prompt[:80]}"
