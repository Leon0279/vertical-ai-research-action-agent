"""API schema for citations."""

from pydantic import BaseModel, Field


class CitationSchema(BaseModel):
    """User-facing citation structure."""

    source: str = Field(..., description="必填字段。最终回答中展示的引用来源句柄，例如 URL、论文 ID 或文档标题。")
    note: str | None = Field(default=None, description="可选字段。说明该来源支撑何种结论或需注意何种限制的简短备注。")
