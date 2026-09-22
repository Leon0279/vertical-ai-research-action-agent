"""User-visible structured details for an assistant history message."""

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.action_item_schema import ActionItemSchema
from app.api.schemas.citation_schema import CitationSchema


class ConversationAssistantDetailsResponse(BaseModel):
    """返回 assistant 历史消息附带的用户可见结构化信息。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    summary: str | None = Field(default=None, description="可选字段。该次回答的简短摘要。")
    recommendation: str | None = Field(default=None, description="可选字段。该次回答的主推荐或主判断。")
    action_items: list[ActionItemSchema] = Field(default_factory=list, description="可选字段。该次回答提供的行动项。")
    citations: list[CitationSchema] = Field(default_factory=list, description="可选字段。该次回答展示的来源引用。")
    confidence: float | None = Field(default=None, description="可选字段。该次回答的整体置信度分数。")
    caveats: list[str] = Field(default_factory=list, description="可选字段。该次回答的限制、风险或未解决事项。")
