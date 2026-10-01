"""Selected material passed to external evidence extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceMaterialSelectionMethod = Literal[
    "full_content",
    "embedding",
    "lexical_fallback",
]


class EvidenceMaterialSelection(BaseModel):
    """Describe the bounded material selected for one external LLM call."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(description="The bounded material content sent to the LLM.")
    selection_method: EvidenceMaterialSelectionMethod
    original_char_count: int = Field(ge=0)
    selected_char_count: int = Field(ge=0)
    total_chunk_count: int = Field(ge=0)
    embedding_candidate_count: int = Field(ge=0)
    selected_chunk_count: int = Field(ge=0)
    degradation_reason: str | None = None
