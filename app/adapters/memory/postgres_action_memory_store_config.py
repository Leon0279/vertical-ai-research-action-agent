"""Configuration for the PostgreSQL action memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_action_memory_store_error import (
    PostgresActionMemoryStoreError,
)
from app.config.env_loader import load_env_file, require_env


class PostgresActionMemoryStoreConfig(BaseModel):
    """提供PostgreSQL行动记忆存储所需的类型化运行时配置。

Typed runtime settings for the action_memory adapter."""

    dsn: str = Field(description="必填字段。连接 PostgreSQL action memory 存储所使用的数据源连接字符串。")
    schema_name: str = Field(default="public", min_length=1, description="action memory 表所在 PostgreSQL schema 名称。")
    table_name: str = Field(default="action_memory", min_length=1, description="保存 ActionMemoryRecord 的 PostgreSQL 表名。")

    @classmethod
    def from_env(cls) -> "PostgresActionMemoryStoreConfig":
        """从环境变量构造 PostgreSQL 行动记忆存储配置。

        Args:
            无显式业务参数。配置从行动记忆 DSN、schema 名称和连接相关环境变量读取。

        Returns:
            PostgresActionMemoryStoreConfig: 已完成环境变量解析的行动记忆存储配置；缺少必填 DSN 时抛出配置异常。
        """

        load_env_file()
        dsn = require_env(
            "POSTGRES_ACTION_MEMORY_DSN",
            PostgresActionMemoryStoreError,
            "POSTGRES_ACTION_MEMORY_DSN is required for action memory.",
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
