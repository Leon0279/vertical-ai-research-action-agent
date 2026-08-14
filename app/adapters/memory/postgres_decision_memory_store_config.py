"""Configuration for the PostgreSQL decision memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_decision_memory_store_error import (
    PostgresDecisionMemoryStoreError,
)
from app.config.env_loader import load_env_file


class PostgresDecisionMemoryStoreConfig(BaseModel):
    """提供PostgreSQL决策记忆存储所需的类型化运行时配置。

Typed runtime settings for the decision_memory adapter."""

    dsn: str = Field(description="必填字段。连接 PostgreSQL decision memory 存储所使用的数据源连接字符串。")
    schema_name: str = Field(default="public", min_length=1, description="decision memory 表所在 PostgreSQL schema 名称。")
    table_name: str = Field(default="decision_memory", min_length=1, description="保存 DecisionMemoryRecord 的 PostgreSQL 表名。")

    @classmethod
    def from_env(cls) -> "PostgresDecisionMemoryStoreConfig":
        """从环境变量构造 PostgreSQL 决策记忆存储配置。

        Args:
            无显式业务参数。配置从决策记忆 DSN、schema 名称和连接相关环境变量读取。

        Returns:
            PostgresDecisionMemoryStoreConfig: 已完成环境变量解析的决策记忆存储配置；缺少必填 DSN 时抛出配置异常。
        """

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
