"""Configuration for the PostgreSQL project profile memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_project_profile_memory_store_error import (
    PostgresProjectProfileMemoryStoreError,
)


class PostgresProjectProfileMemoryStoreConfig(BaseModel):
    """Typed runtime settings for the project_profile_memory adapter."""

    dsn: str
    schema_name: str = Field(default="public", min_length=1)
    table_name: str = Field(default="project_profile_memory", min_length=1)

    @classmethod
    def from_env(cls) -> "PostgresProjectProfileMemoryStoreConfig":
        """Build config from environment variables."""

        dsn = os.getenv("POSTGRES_PROJECT_PROFILE_MEMORY_DSN", "").strip()
        if not dsn:
            raise PostgresProjectProfileMemoryStoreError(
                "POSTGRES_PROJECT_PROFILE_MEMORY_DSN is required for project profile memory."
            )

        return cls(
            dsn=dsn,
            schema_name=os.getenv(
                "POSTGRES_PROJECT_PROFILE_MEMORY_SCHEMA",
                cls.model_fields["schema_name"].default,
            ),
            table_name=os.getenv(
                "POSTGRES_PROJECT_PROFILE_MEMORY_TABLE",
                cls.model_fields["table_name"].default,
            ),
        )
