"""Configuration for the PostgreSQL project profile memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_project_profile_memory_store_error import (
    PostgresProjectProfileMemoryStoreError,
)
from app.config.env_loader import load_env_file


class PostgresProjectProfileMemoryStoreConfig(BaseModel):
    """提供PostgreSQL项目档案记忆存储所需的类型化运行时配置。

Typed runtime settings for the project_profile_memory adapter."""

    dsn: str = Field(description="必填字段。连接 PostgreSQL project profile memory 存储所使用的数据源连接字符串。")
    schema_name: str = Field(default="public", min_length=1, description="project profile memory 表所在 PostgreSQL schema 名称。")
    table_name: str = Field(default="project_profile_memory", min_length=1, description="保存 ProjectProfileMemoryRecord 的 PostgreSQL 表名。")

    @classmethod
    def from_env(cls) -> "PostgresProjectProfileMemoryStoreConfig":
        """Build config from environment variables."""

        load_env_file()
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
