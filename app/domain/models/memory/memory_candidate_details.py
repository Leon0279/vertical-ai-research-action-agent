"""Memory-type-aware candidate details parsing."""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel

from app.domain.enums.memory_type import MemoryType
from app.domain.models.memory.action_execution_candidate_details import (
    ActionExecutionCandidateDetails,
)
from app.domain.models.memory.decision_candidate_details import DecisionCandidateDetails
from app.domain.models.memory.preference_policy_candidate_details import (
    PreferencePolicyCandidateDetails,
)
from app.domain.models.memory.project_profile_candidate_details import (
    ProjectProfileCandidateDetails,
)
from app.domain.models.memory.research_knowledge_candidate_details import (
    ResearchKnowledgeCandidateDetails,
)
from app.domain.models.memory.tracking_watchlist_candidate_details import (
    TrackingWatchlistCandidateDetails,
)

MemoryCandidateDetails = (
    ProjectProfileCandidateDetails
    | DecisionCandidateDetails
    | ActionExecutionCandidateDetails
    | PreferencePolicyCandidateDetails
    | ResearchKnowledgeCandidateDetails
    | TrackingWatchlistCandidateDetails
)

_DETAILS_MODEL_BY_MEMORY_TYPE: dict[MemoryType, type[BaseModel]] = {
    MemoryType.PROJECT_PROFILE: ProjectProfileCandidateDetails,
    MemoryType.DECISION: DecisionCandidateDetails,
    MemoryType.ACTION_EXECUTION: ActionExecutionCandidateDetails,
    MemoryType.PREFERENCE: PreferencePolicyCandidateDetails,
    MemoryType.RESEARCH_POLICY: PreferencePolicyCandidateDetails,
    MemoryType.RESEARCH_KNOWLEDGE: ResearchKnowledgeCandidateDetails,
    MemoryType.TRACKING_WATCHLIST: TrackingWatchlistCandidateDetails,
}


def parse_memory_candidate_details(
    memory_type: MemoryType | str,
    value: Any,
) -> MemoryCandidateDetails:
    """Parse details with the model selected by the candidate's memory type."""

    normalized_memory_type = MemoryType(memory_type)
    model = _DETAILS_MODEL_BY_MEMORY_TYPE[normalized_memory_type]
    return cast(MemoryCandidateDetails, model.model_validate(value))


def memory_candidate_details_match_type(
    memory_type: MemoryType,
    details: MemoryCandidateDetails,
) -> bool:
    """Return whether a parsed details instance matches its owning memory type."""

    return isinstance(details, _DETAILS_MODEL_BY_MEMORY_TYPE[memory_type])
