"""Configuration for the PostgreSQL preference/policy memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_preference_policy_memory_store_error import (
    PostgresPreferencePolicyMemoryStoreError,
)


class PostgresPreferencePolicyMemoryStoreConfig(BaseModel):
    """Typed runtime settings for the preference_policy_memory adapter."""

    dsn: str
    schema_name: str = Field(default="public", min_length=1)
    table_name: str = Field(default="preference_policy_memory", min_length=1)
    system_user_id: str = Field(default="__system__", min_length=1)

    @classmethod
    def from_env(cls) -> "PostgresPreferencePolicyMemoryStoreConfig":
        """Build config from environment variables."""

        dsn = os.getenv("POSTGRES_PREFERENCE_POLICY_MEMORY_DSN", "").strip()
        if not dsn:
            raise PostgresPreferencePolicyMemoryStoreError(
                "POSTGRES_PREFERENCE_POLICY_MEMORY_DSN is required for preference/policy memory."
            )

        return cls(
            dsn=dsn,
            schema_name=os.getenv(
                "POSTGRES_PREFERENCE_POLICY_MEMORY_SCHEMA",
                cls.model_fields["schema_name"].default,
            ),
            table_name=os.getenv(
                "POSTGRES_PREFERENCE_POLICY_MEMORY_TABLE",
                cls.model_fields["table_name"].default,
            ),
            system_user_id=os.getenv(
                "POSTGRES_PREFERENCE_POLICY_MEMORY_SYSTEM_USER_ID",
                cls.model_fields["system_user_id"].default,
            ),
        )
