"""Typed retrieval trace for runtime retrieval outputs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.domain.models.retrieval.retrieval_attempt_trace import RetrievalAttemptTrace


class RetrievalTrace(BaseModel):
    """Task and provenance trace shared by retrieval outputs."""

    target_problem: str | None = Field(default=None, description="Target problem used for retrieval.")
    selected_family: str | None = Field(default=None, description="Selected retrieval family.")
    selected_tool: str | None = Field(default=None, description="Concrete tool selected inside the family.")
    generated_query: str | None = Field(default=None, description="Generated query used for retrieval.")
    query_focus: str | None = Field(default=None, description="LLM-provided query focus, if available.")
    acquisition_status: str | None = Field(default=None, description="Final acquisition status.")
    attempts: list[RetrievalAttemptTrace] = Field(default_factory=list)
    returned_refs: list[str] = Field(default_factory=list)
    errors: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _from_legacy_mapping(cls, value: Any) -> Any:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        known = {
            "target_problem",
            "selected_family",
            "selected_tool",
            "generated_query",
            "query_focus",
            "acquisition_status",
            "attempts",
            "returned_refs",
            "errors",
            "context",
            "observability",
        }
        errors = dict(value.get("errors") or {}) if isinstance(value.get("errors"), Mapping) else {}
        context = dict(value.get("context") or {}) if isinstance(value.get("context"), Mapping) else {}
        observability = (
            dict(value.get("observability") or {})
            if isinstance(value.get("observability"), Mapping)
            else {}
        )
        for key, item in value.items():
            if key in known:
                continue
            if key.endswith("_error") or key in {"family_exception", "family_error"}:
                errors[key] = item
            elif key in {
                "query_text",
                "target_scope",
                "evidence_goal",
                "sub_question",
                "comparison_candidate",
                "gap",
                "freshness_requirement",
                "source_names",
                "include_domains",
                "exclude_domains",
                "owner_user_id",
                "project_scope_id",
                "allowed_visibility_scopes",
                "knowledge_types",
                "topic_tags",
                "source_types",
                "selected_sources",
                "preferred_tool",
                "candidate_tools",
                "used_query_embedding",
            }:
                context[key] = item
            else:
                observability[key] = item
        return {
            "target_problem": value.get("target_problem"),
            "selected_family": value.get("selected_family"),
            "selected_tool": value.get("selected_tool"),
            "generated_query": value.get("generated_query"),
            "query_focus": value.get("query_focus"),
            "acquisition_status": value.get("acquisition_status"),
            "attempts": value.get("attempts") or [],
            "returned_refs": value.get("returned_refs") or [],
            "errors": errors,
            "context": context,
            "observability": observability,
        }

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.context:
            return self.context[key]
        if key in self.errors:
            return self.errors[key]
        return self.observability.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if (
            value is None
            and key not in self.context
            and key not in self.errors
            and key not in self.observability
            and not hasattr(self, key)
        ):
            raise KeyError(key)
        return value

    def __iter__(self):
        yield from self.to_legacy_dict().items()

    def to_legacy_dict(self) -> dict[str, Any]:
        data = {
            "target_problem": self.target_problem,
            "selected_family": self.selected_family,
            "selected_tool": self.selected_tool,
            "generated_query": self.generated_query,
            "query_focus": self.query_focus,
            "acquisition_status": self.acquisition_status,
            "attempts": [attempt.to_legacy_dict() for attempt in self.attempts],
            "returned_refs": self.returned_refs,
        }
        data.update(self.context)
        data.update(self.errors)
        data.update(self.observability)
        return data
