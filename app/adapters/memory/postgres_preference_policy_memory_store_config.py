"""Configuration for the PostgreSQL preference/policy memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_preference_policy_memory_store_error import (
    PostgresPreferencePolicyMemoryStoreError,
)
from app.config.env_loader import load_env_file


class PostgresPreferencePolicyMemoryStoreConfig(BaseModel):
    """Typed runtime settings for the preference_policy_memory adapter."""

    dsn: str = Field(description="必填字段。连接 PostgreSQL preference/policy memory 存储所使用的数据源连接字符串。")
    schema_name: str = Field(default="public", min_length=1, description="preference/policy memory 表所在 PostgreSQL schema 名称。")
    table_name: str = Field(default="preference_policy_memory", min_length=1, description="保存 PreferencePolicyMemoryRecord 的 PostgreSQL 表名。")
    system_user_id: str = Field(default="__system__", min_length=1, description="系统级 policy record 使用的用户标识，用于与真实用户范围区分。")

    @classmethod
    def from_env(cls) -> "PostgresPreferencePolicyMemoryStoreConfig":
        """Build config from environment variables."""

        load_env_file()
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
