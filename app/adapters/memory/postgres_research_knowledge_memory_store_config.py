"""Configuration for the PostgreSQL research knowledge memory adapter."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.memory.postgres_research_knowledge_memory_store_error import (
    PostgresResearchKnowledgeMemoryStoreError,
)
from app.config.env_loader import load_env_file


class PostgresResearchKnowledgeMemoryStoreConfig(BaseModel):
    """提供PostgreSQL研究知识记忆存储所需的类型化运行时配置。

Typed runtime settings for the research_knowledge_units adapter."""

    dsn: str = Field(description="必填字段。连接 PostgreSQL research knowledge memory 存储所使用的数据源连接字符串。")
    schema_name: str = Field(default="public", min_length=1, description="research knowledge unit 表所在 PostgreSQL schema 名称。")
    table_name: str = Field(default="research_knowledge_units", min_length=1, description="保存 ResearchKnowledgeUnitRecord 的 PostgreSQL 表名。")
    max_recall_limit: int = Field(default=20, ge=1, description="单次 research knowledge recall 允许返回的最大 unit 数量。")

    @classmethod
    def from_env(cls) -> "PostgresResearchKnowledgeMemoryStoreConfig":
        """从环境变量构造 PostgreSQL 研究知识记忆存储配置。

        Args:
            无显式业务参数。配置从研究知识记忆 DSN、schema、召回数量上限和连接相关环境变量读取。

        Returns:
            PostgresResearchKnowledgeMemoryStoreConfig: 已完成环境变量解析的研究知识记忆存储配置；缺少必填 DSN 时抛出配置异常。
        """

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
