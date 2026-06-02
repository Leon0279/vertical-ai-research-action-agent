"""Configuration for the PostgreSQL action memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_action_memory_store_error import (
    PostgresActionMemoryStoreError,
)


class PostgresActionMemoryStoreConfig(BaseModel):
    """Typed runtime settings for the action_memory adapter."""

    dsn: str
    schema_name: str = Field(default="public", min_length=1)
    table_name: str = Field(default="action_memory", min_length=1)

    @classmethod
    def from_env(cls) -> "PostgresActionMemoryStoreConfig":
        """Build config from environment variables."""

        dsn = os.getenv("POSTGRES_ACTION_MEMORY_DSN", "").strip()
        if not dsn:
            raise PostgresActionMemoryStoreError(
                "POSTGRES_ACTION_MEMORY_DSN is required for action memory."
            )

        return cls(
            dsn=dsn,
            schema_name=os.getenv(
                "POSTGRES_ACTION_MEMORY_SCHEMA",
                cls.model_fields["schema_name"].default,
            ),
            table_name=os.getenv(
                "POSTGRES_ACTION_MEMORY_TABLE",
                cls.model_fields["table_name"].default,
            ),
        )
