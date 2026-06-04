"""Embedding generation result model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingResult(BaseModel):
    """One embedding vector returned by an embedding adapter."""

    model_config = ConfigDict(extra="forbid")

    text_index: int = Field(
        ge=0,
        description="Index of the input text this embedding belongs to.",
    )
    embedding: list[float] = Field(
        min_length=1,
        description="Embedding vector returned by the provider.",
    )
    model: str = Field(
        min_length=1,
        description="Embedding model used to generate the vector.",
    )
    dimensions: int = Field(
        gt=0,
        description="Embedding vector dimension.",
    )
    prompt_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Prompt token usage reported by the provider, when available.",
    )
    total_tokens: int | None = Field(
        default=None,
        ge=0,
        description="Total token usage reported by the provider, when available.",
    )
