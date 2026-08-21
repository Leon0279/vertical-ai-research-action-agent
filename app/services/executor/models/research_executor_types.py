"""Research Executor 内部使用的类型别名。"""

from __future__ import annotations

from typing import Literal

from app.services.executor.models.evidence_coverage_entry import (
    EvidenceCoverageStatus,
    EvidenceCoverageTargetType,
)

ResearchIterationOutcome = Literal["continue", "stop", "degrade"]
ResearchActionMode = Literal[
    "refine_from_existing_state",
    "memory_backed_acquisition",
    "external_acquisition",
]
ResearchCoverageStatus = EvidenceCoverageStatus
ResearchSupportStrength = Literal[
    "strong_enough",
    "weak_support",
    "conflicting_support",
    "insufficient_support",
]
ResearchFindingMaturity = Literal["tentative", "partially_stable", "stable", "blocked"]
ResearchGapScope = Literal[
    "objective_level",
    "sub_question_level",
    "comparison_level",
    "candidate_level",
    "dimension_level",
    "finding_level",
    "recommendation_readiness_level",
]
ResearchGapNature = Literal[
    "missing",
    "weak",
    "ambiguous",
    "conflicting",
    "imbalanced",
    "stale",
    "not_actionable",
    "none",
]
ResearchGapSeverity = Literal["blocking", "important", "optional", "none"]
ResearchNeedPurpose = Literal[
    "establish_coverage",
    "strengthen_support",
    "resolve_ambiguity",
    "resolve_conflict",
    "rebalance_comparison",
    "refresh_status",
    "improve_actionability",
    "none",
]
ResearchDesiredEvidenceKind = Literal[
    "direct_fact",
    "stronger_supporting_evidence",
    "disambiguating_evidence",
    "comparison_evidence",
    "fresh_status_evidence",
    "decision_supporting_evidence",
    "none",
]
ResearchFreshnessRequirement = Literal["normal", "fresh_preferred", "fresh_required", "none"]
ResearchMinimumSupportRequirement = Literal[
    "any_relevant_signal",
    "moderate_support",
    "strong_support",
    "none",
]
ResearchCoverageTargetType = EvidenceCoverageTargetType
ResearchTopGapProgress = Literal[
    "resolved",
    "partially_advanced",
    "not_advanced",
    "regressed",
]
ResearchEvidenceGain = Literal[
    "meaningful_gain",
    "limited_gain",
    "no_meaningful_gain",
    "failed_acquisition",
]
ResearchFindingProgress = Literal[
    "improved_to_stable",
    "improved_but_not_stable",
    "no_material_change",
    "became_less_certain",
]
ResearchResidualUncertainty = Literal["high", "moderate", "low", "minimal"]

REFINE_ACTION_MODE: ResearchActionMode = "refine_from_existing_state"
MEMORY_ACTION_MODE: ResearchActionMode = "memory_backed_acquisition"
EXTERNAL_ACTION_MODE: ResearchActionMode = "external_acquisition"
