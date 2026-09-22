"""Typed user-visible details attached to an assistant history message."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.action_item import ActionItem
from app.domain.models.citation import Citation


class ConversationAssistantDetails(BaseModel):
    """表示历史 assistant 消息附带的用户可见结构化信息。"""

    model_config = ConfigDict(extra="ignore")

    summary: str | None = Field(
        default=None,
        description="可选字段。该次 assistant 回答的简短摘要。",
    )
    recommendation: str | None = Field(
        default=None,
        description="可选字段。该次回答给出的结构化主推荐或主判断。",
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="可选字段。该次回答向用户提供的结构化行动项。",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="可选字段。该次回答向用户展示的来源引用。",
    )
    confidence: float | None = Field(
        default=None,
        description="可选字段。该次回答的整体置信度分数。",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="可选字段。该次回答向用户说明的限制、风险或未解决事项。",
    )
