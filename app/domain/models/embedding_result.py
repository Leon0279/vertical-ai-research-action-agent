"""Embedding generation result model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingResult(BaseModel):
    """表示嵌入的处理结果。

One embedding vector returned by an embedding adapter."""

    model_config = ConfigDict(extra="forbid")

    text_index: int = Field(
        ge=0,
        description="必填字段。该 embedding 对应输入文本在当前批次中的索引位置。",
    )
    embedding: list[float] = Field(
        min_length=1,
        description="必填字段。embedding provider 返回的向量数值列表。",
    )
    model: str = Field(
        min_length=1,
        description="必填字段。生成该向量时实际调用的 embedding 模型名称。",
    )
    dimensions: int = Field(
        gt=0,
        description="必填字段。该 embedding 向量的维度。",
    )
    prompt_tokens: int | None = Field(
        default=None,
        ge=0,
        description="可选字段。provider 返回的 prompt token 使用量；provider 未提供时为 None。",
    )
    total_tokens: int | None = Field(
        default=None,
        ge=0,
        description="可选字段。provider 返回的总 token 使用量；provider 未提供时为 None。",
    )
