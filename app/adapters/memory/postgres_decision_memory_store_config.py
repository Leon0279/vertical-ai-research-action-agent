"""Configuration for the PostgreSQL decision memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_decision_memory_store_error import (
    PostgresDecisionMemoryStoreError,
)
from app.config.env_loader import load_env_file


class PostgresDecisionMemoryStoreConfig(BaseModel):
    """Typed runtime settings for the decision_memory adapter."""

    dsn: str
    schema_name: str = Field(default="public", min_length=1)
    table_name: str = Field(default="decision_memory", min_length=1)

    @classmethod
    def from_env(cls) -> "PostgresDecisionMemoryStoreConfig":
        """Build config from environment variables."""

        load_env_file()
        dsn = os.getenv("POSTGRES_DECISION_MEMORY_DSN", "").strip()
        if not dsn:
            raise PostgresDecisionMemoryStoreError(
                "POSTGRES_DECISION_MEMORY_DSN is required for decision memory."
            )

        return cls(
            dsn=dsn,
            schema_name=os.getenv(
                "POSTGRES_DECISION_MEMORY_SCHEMA",
                cls.model_fields["schema_name"].default,
            ),
            table_name=os.getenv(
                "POSTGRES_DECISION_MEMORY_TABLE",
                cls.model_fields["table_name"].default,
            ),
        )
