"""Evidence shape model for family-level retrieval intent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DesiredEvidenceKind = Literal[
    "direct_fact",
    "supporting_evidence",
    "disambiguating_evidence",
    "comparison_evidence",
    "status_evidence",
]
FreshnessRequirement = Literal["normal", "fresh_preferred", "fresh_required"]
EvidenceBreadth = Literal["narrow", "normal", "broad"]


class EvidenceShape(BaseModel):
    """Expected shape of evidence for a retrieval acquisition path."""

    desired_evidence_kind: DesiredEvidenceKind = Field(
        default="supporting_evidence",
        description="The kind of evidence expected from the selected retrieval family.",
    )
    freshness_requirement: FreshnessRequirement = Field(
        default="normal",
        description="How strongly this retrieval path should prefer fresh information.",
    )
    breadth: EvidenceBreadth = Field(
        default="normal",
        description="How narrow or broad this retrieval path should be.",
    )
