"""Supporting context item retained outside core running state."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextItem(BaseModel):
    """Selected supporting context retained outside core running state."""

    id: str = Field(
        min_length=1,
        description="Stable identifier for this selected supporting context item.",
    )
    source_type: str = Field(
        min_length=1,
        description=(
            "Source category for this context item, such as session_memory, "
            "project_profile, decision_memory, research_memory, or tool_result."
        ),
    )
    scope_id: str | None = Field(
        default=None,
        description="Optional scope identifier associated with this supporting context item.",
    )
    summary: str = Field(
        min_length=1,
        description=(
            "Directly consumable summary-level content for this context item. "
            "It should stay concise and should not default to large raw payloads."
        ),
    )
    priority: int = Field(
        description="Priority signal used when selecting or retaining supporting context under budget.",
    )
    freshness_tag: str | None = Field(
        default=None,
        description="Optional freshness indicator for this context item, such as fresh, aging, or stale.",
    )
    confidence: str | None = Field(
        default=None,
        description="Optional confidence label for this context item, such as low, medium, or high.",
    )
    can_assimilate_to_state: bool = Field(
        default=False,
        description="Whether this supporting item is suitable to be assimilated into RunningState if it becomes core context.",
    )
    usage_hint: str | None = Field(
        default=None,
        description=(
            "Optional hint about where this item is most useful, such as planning_only, "
            "research_support, or conclusion_support."
        ),
    )
