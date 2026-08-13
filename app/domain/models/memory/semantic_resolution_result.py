"""Semantic relation result used by memory persistence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SemanticResolutionRelation = Literal[
    "no_existing_record",
    "duplicate",
    "same_entity_changed",
    "state_transition",
    "conflict",
    "unrelated",
]


class SemanticResolutionResult(BaseModel):
    """确定性判断一个 memory candidate 与已有记录关系的结果。"""

    relation: SemanticResolutionRelation = Field(
        description=(
            "candidate 与已有 typed memory record 的关系。该字段只表达语义关系，"
            "不直接等同于最终 persistence action。"
        ),
    )
    matched_record_ids: list[str] = Field(
        default_factory=list,
        description=(
            "本次规则判断实际比较过的已有记录标识。没有已有记录或没有可识别记录时为空。"
        ),
    )
    primary_record_id: str | None = Field(
        default=None,
        description="本次关系判断中最主要的关联记录标识；没有明确关联对象时为空。",
    )
    rationale: str = Field(
        min_length=1,
        description="解释规则如何得出当前关系的简短原因，供 persistence 和调试使用。",
    )
