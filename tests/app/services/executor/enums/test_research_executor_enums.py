"""Research Executor service-private 枚举测试。"""

from enum import StrEnum

import pytest
from pydantic import TypeAdapter, ValidationError

from app.services.executor import enums


EXPECTED_ENUM_VALUES: dict[str, list[str]] = {
    "ResearchIterationOutcome": ["continue", "stop", "degrade"],
    "ResearchActionMode": [
        "refine_from_existing_state",
        "memory_backed_acquisition",
        "external_acquisition",
    ],
    "ResearchCoverageStatus": [
        "covered",
        "partially_covered",
        "not_covered",
    ],
    "ResearchCoverageTargetType": [
        "objective",
        "sub_question",
        "comparison_candidate",
    ],
    "ResearchSupportStrength": [
        "strong_enough",
        "moderate_support",
        "weak_support",
        "conflicting_support",
        "insufficient_support",
    ],
    "ResearchFindingMaturity": [
        "tentative",
        "partially_stable",
        "stable",
        "blocked",
    ],
    "ResearchGapScope": [
        "objective_level",
        "sub_question_level",
        "comparison_level",
        "candidate_level",
        "dimension_level",
        "finding_level",
        "recommendation_readiness_level",
    ],
    "ResearchGapNature": [
        "missing",
        "weak",
        "ambiguous",
        "conflicting",
        "imbalanced",
        "stale",
        "not_actionable",
        "none",
    ],
    "ResearchGapSeverity": ["blocking", "important", "optional", "none"],
    "ResearchNeedPurpose": [
        "establish_coverage",
        "strengthen_support",
        "resolve_ambiguity",
        "resolve_conflict",
        "rebalance_comparison",
        "refresh_status",
        "improve_actionability",
        "none",
    ],
    "ResearchDesiredEvidenceKind": [
        "direct_fact",
        "stronger_supporting_evidence",
        "disambiguating_evidence",
        "comparison_evidence",
        "fresh_status_evidence",
        "decision_supporting_evidence",
        "none",
    ],
    "ResearchFreshnessRequirement": [
        "normal",
        "fresh_preferred",
        "fresh_required",
        "none",
    ],
    "ResearchMinimumSupportRequirement": [
        "any_relevant_signal",
        "moderate_support",
        "strong_support",
        "none",
    ],
    "ResearchTopGapProgress": [
        "resolved",
        "partially_advanced",
        "not_advanced",
        "regressed",
    ],
    "ResearchEvidenceGain": [
        "meaningful_gain",
        "limited_gain",
        "no_meaningful_gain",
        "failed_acquisition",
    ],
    "ResearchFindingProgress": [
        "improved_to_stable",
        "improved_but_not_stable",
        "no_material_change",
        "became_less_certain",
    ],
    "ResearchResidualUncertainty": ["high", "moderate", "low", "minimal"],
}


@pytest.mark.parametrize("enum_name", EXPECTED_ENUM_VALUES)
def test_research_executor_enum_values_and_json_wire_format(enum_name: str) -> None:
    enum_type = getattr(enums, enum_name)
    expected_values = EXPECTED_ENUM_VALUES[enum_name]

    assert issubclass(enum_type, StrEnum)
    assert [member.value for member in enum_type] == expected_values

    adapter = TypeAdapter(enum_type)
    for value in expected_values:
        parsed = adapter.validate_python(value)
        assert isinstance(parsed, enum_type)
        assert parsed.value == value
        assert str(parsed) == value
        assert adapter.dump_python(parsed, mode="json") == value


@pytest.mark.parametrize("enum_name", EXPECTED_ENUM_VALUES)
def test_research_executor_enum_rejects_unknown_wire_value(enum_name: str) -> None:
    enum_type = getattr(enums, enum_name)

    with pytest.raises(ValidationError):
        TypeAdapter(enum_type).validate_python("unknown_research_enum_value")


def test_executor_enum_package_exports_all_expected_types() -> None:
    assert set(enums.__all__) == set(EXPECTED_ENUM_VALUES)
