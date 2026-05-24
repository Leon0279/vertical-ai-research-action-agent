"""LLM adapter stubs."""

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.adapters.llm.stub_llm_client import StubLLMClient

__all__ = ["LLMClientProtocol", "StubLLMClient"]
