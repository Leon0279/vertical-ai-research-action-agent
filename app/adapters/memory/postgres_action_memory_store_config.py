"""Configuration for the PostgreSQL action memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_action_memory_store_error import (
    PostgresActionMemoryStoreError,
)
from app.config.env_loader import load_env_file


class PostgresActionMemoryStoreConfig(BaseModel):
    """Typed runtime settings for the action_memory adapter."""

    dsn: str = Field(description="必填字段。连接 PostgreSQL action memory 存储所使用的数据源连接字符串。")
    schema_name: str = Field(default="public", min_length=1, description="action memory 表所在 PostgreSQL schema 名称。")
    table_name: str = Field(default="action_memory", min_length=1, description="保存 ActionMemoryRecord 的 PostgreSQL 表名。")

    @classmethod
    def from_env(cls) -> "PostgresActionMemoryStoreConfig":
        """Build config from environment variables."""

        load_env_file()
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
