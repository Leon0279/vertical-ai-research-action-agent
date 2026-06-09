"""Configuration for the PostgreSQL research knowledge memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_research_knowledge_memory_store_error import (
    PostgresResearchKnowledgeMemoryStoreError,
)
from app.config.env_loader import load_env_file


class PostgresResearchKnowledgeMemoryStoreConfig(BaseModel):
    """Typed runtime settings for the research_knowledge_units adapter."""

    dsn: str
    schema_name: str = Field(default="public", min_length=1)
    table_name: str = Field(default="research_knowledge_units", min_length=1)
    max_recall_limit: int = Field(default=20, ge=1)

    @classmethod
    def from_env(cls) -> "PostgresResearchKnowledgeMemoryStoreConfig":
        """Build config from environment variables."""

        load_env_file()
        dsn = os.getenv("POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_DSN", "").strip()
        if not dsn:
            raise PostgresResearchKnowledgeMemoryStoreError(
                "POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_DSN is required for research knowledge memory."
            )

        max_recall_limit = os.getenv(
            "POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_MAX_RECALL_LIMIT",
            str(cls.model_fields["max_recall_limit"].default),
        )

        return cls(
            dsn=dsn,
            schema_name=os.getenv(
                "POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_SCHEMA",
                cls.model_fields["schema_name"].default,
            ),
            table_name=os.getenv(
                "POSTGRES_RESEARCH_KNOWLEDGE_MEMORY_TABLE",
                cls.model_fields["table_name"].default,
            ),
            max_recall_limit=int(max_recall_limit),
        )
