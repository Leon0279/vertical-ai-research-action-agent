"""Domain model for conclusion results."""

from pydantic import BaseModel, Field

from app.domain.models.action_item import ActionItem
from app.domain.models.citation import Citation
from app.domain.models.conclusion.final_recommendation import FinalRecommendation


class ConclusionResult(BaseModel):
    """表示结论的处理结果。

Aggregated structured conclusion."""

    summary: str = Field(description="必填字段。结论的简短摘要，用于快速表达当前回答的核心信息，不承载完整用户答案。")
    recommendation: FinalRecommendation | None = Field(
        default=None,
        description="可选字段。结构化主推荐或主判断；纯信息型回答没有明确推荐时为 None。",
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="可选字段，默认空列表。由结论提取出的可执行下一步，不应为了填充结构生成泛化事项。",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="可选字段，默认空列表。支撑结论的展示级来源引用；完整来源 provenance 仍由 SourceReference 维护。",
    )
    confidence: float | None = Field(
        default=None,
        description="可选字段。结论整体可信度的数值表示；尚未形成可评估结论时为 None。",
    )
