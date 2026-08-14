"""Query object for research knowledge semantic recall."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ResearchKnowledgeRecallQuery(BaseModel):
    """表示从研究知识库召回信息的查询条件。

Metadata filters plus a precomputed query embedding for knowledge recall."""

    model_config = ConfigDict(extra="forbid")

    owner_user_id: str = Field(
        min_length=1,
        description="必填字段。当前 recall 请求的用户归属边界，用于隔离不同用户的 research knowledge。",
    )
    query_embedding: list[float] = Field(
        min_length=1,
        description="必填字段。已经生成的查询 embedding 向量，adapter 用它进行语义召回。",
    )
    allowed_visibility_scopes: list[str] = Field(
        default_factory=lambda: ["user"],
        description="可选字段，默认仅 user。当前读取路径允许访问的 visibility scope 列表。",
    )
    project_scope_id: str | None = Field(
        default=None,
        description="可选字段。用于项目范围 knowledge recall 的 project scope 标识；没有项目上下文时为 None。",
    )
    knowledge_types: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。按 knowledge_type 限制 recall 结果的过滤条件。",
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。按 topic tag 重合度限制 recall 结果的过滤条件。",
    )
    source_types: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。按原始 source type 限制 recall 结果的过滤条件。",
    )
    limit: int = Field(
        default=5,
        ge=1,
        description="请求的 recall 数量上限；adapter 还会依据自身 max limit 进行进一步裁剪。",
    )
