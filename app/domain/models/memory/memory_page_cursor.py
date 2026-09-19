"""Versioned cursor model for memory collection pagination."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.models.memory.action_memory_status import ActionMemoryStatus
from app.domain.models.memory.research_knowledge_visibility_scope import (
    ResearchKnowledgeVisibilityScope,
)


class MemoryPageCursor(BaseModel):
    """表示客户端不可见语义下的稳定 Memory keyset 游标。"""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    collection: Literal[
        "decisions",
        "actions",
        "policies",
        "research_knowledge",
    ]
    updated_at: datetime
    record_id: str = Field(min_length=1)
    action_statuses: list[ActionMemoryStatus] | None = None
    visibility_scopes: list[ResearchKnowledgeVisibilityScope] | None = None

    @field_validator("updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject ambiguous timestamps that cannot define a stable global order."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_collection_filters(self) -> "MemoryPageCursor":
        """Keep collection-specific filters bound to the correct cursor type."""

        if self.collection == "decisions":
            if self.action_statuses is not None:
                raise ValueError("decision cursors cannot contain action statuses")
            if self.visibility_scopes is not None:
                raise ValueError("decision cursors cannot contain visibility scopes")
            return self

        if self.collection == "policies":
            if self.action_statuses is not None:
                raise ValueError("policy cursors cannot contain action statuses")
            if self.visibility_scopes is not None:
                raise ValueError("policy cursors cannot contain visibility scopes")
            return self

        if self.collection == "research_knowledge":
            if self.action_statuses is not None:
                raise ValueError(
                    "research knowledge cursors cannot contain action statuses"
                )
            if not self.visibility_scopes:
                raise ValueError(
                    "research knowledge cursors require at least one visibility scope"
                )
            if len(self.visibility_scopes) != len(set(self.visibility_scopes)):
                raise ValueError(
                    "research knowledge cursor visibility scopes must be unique"
                )
            return self

        if self.visibility_scopes is not None:
            raise ValueError("action cursors cannot contain visibility scopes")
        if not self.action_statuses:
            raise ValueError("action cursors require at least one action status")
        if len(self.action_statuses) != len(set(self.action_statuses)):
            raise ValueError("action cursor statuses must be unique")
        return self
