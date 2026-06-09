"""Shared test environment defaults."""

from __future__ import annotations

import os


def pytest_configure() -> None:
    """Provide minimal env for default runtime dependency construction in tests."""

    os.environ.setdefault("VAA_SKIP_DOTENV", "1")
    os.environ.setdefault("REDIS_SESSION_MEMORY_URL", "redis://127.0.0.1:1/0")
    os.environ.setdefault("POSTGRES_PROJECT_PROFILE_MEMORY_DSN", "postgresql://127.0.0.1:1/test")
    os.environ.setdefault("POSTGRES_DECISION_MEMORY_DSN", "postgresql://127.0.0.1:1/test")
    os.environ.setdefault("POSTGRES_ACTION_MEMORY_DSN", "postgresql://127.0.0.1:1/test")
    os.environ.setdefault("POSTGRES_PREFERENCE_POLICY_MEMORY_DSN", "postgresql://127.0.0.1:1/test")
    os.environ.setdefault("POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_DSN", "postgresql://127.0.0.1:1/test")
    os.environ.setdefault("ZHIPU_API_KEY", "test-zhipu-api-key")
    os.environ.setdefault("ZHIPU_EMBEDDING_BASE_URL", "http://127.0.0.1:1/api/paas/v4")
    os.environ.setdefault("ZHIPU_EMBEDDING_TIMEOUT_SECONDS", "0.1")
    os.environ.setdefault("ARXIV_PAPER_CONTENT_FETCH_USER_AGENT", "vaa-test-agent/1.0")
