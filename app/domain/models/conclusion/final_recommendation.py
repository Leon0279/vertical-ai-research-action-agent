"""Domain model for final recommendations."""

from pydantic import BaseModel, Field


class FinalRecommendation(BaseModel):
    """Recommendation output."""

    recommendation: str = Field(description="必填字段。最终推荐、决策方向或主判断的简短表达，供用户和下游结构化消费。")
    rationale: str | None = Field(
        default=None,
        description="可选字段。推荐成立的主要依据、取舍或适用条件；没有单独说明时为 None。",
    )
    deferred_options: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。当前未采用但可在后续条件满足时重新评估的备选方案。",
    )
