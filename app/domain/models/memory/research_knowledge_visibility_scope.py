"""Supported visibility scopes for Research Knowledge browsing."""

from typing import Literal, TypeAlias

ResearchKnowledgeVisibilityScope: TypeAlias = Literal[
    "user",
    "project",
    "domain",
    "global",
]
