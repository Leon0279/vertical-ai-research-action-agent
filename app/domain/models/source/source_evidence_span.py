"""Source evidence span model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class SourceEvidenceSpan(BaseModel):
    """描述 evidence 在原始 source 内部的位置。"""

    page: int | None = Field(
        default=None,
        ge=1,
        description=(
            "可选字段，当前暂不使用。PDF、论文、文档等分页来源中的 1-based 页码。"
            "当前相关 adapter 暂不保留 page-level mapping，因此不要在迁移时伪造该值；"
            "未来 paper_content_fetch 如果保留 PDF page mapping，可填充该字段。"
        ),
    )
    section: str | None = Field(
        default=None,
        description=(
            "可选字段。来源中的章节、标题、anchor、docs section 或语义 section label。"
            "当前 docs_search adapter 可由 DocsSearchResult.section 填充；"
            "其它 adapter 如果没有可靠 section 信息，应保持为空。"
        ),
    )
    paragraph: int | None = Field(
        default=None,
        ge=1,
        description=(
            "可选字段，当前暂不使用。来源正文中的 1-based 段落序号。"
            "当前 adapter 暂不保存 paragraph index，因此不要根据 snippet 反推；"
            "未来 docs/web extraction 如果保留段落索引，可填充该字段。"
        ),
    )
    line_start: int | None = Field(
        default=None,
        ge=1,
        description=(
            "可选字段，当前暂不使用。文本、代码、日志等 line-addressable source "
            "中的 1-based 起始行号。当前相关 adapter 暂不返回 line range；"
            "未来 code/file source adapter 可填充该字段。"
        ),
    )
    line_end: int | None = Field(
        default=None,
        ge=1,
        description=(
            "可选字段，当前暂不使用。文本、代码、日志等 line-addressable source "
            "中的 1-based 结束行号，包含该行。当前相关 adapter 暂不返回 line range；"
            "未来 code/file source adapter 可填充该字段。"
        ),
    )
    char_start: int | None = Field(
        default=None,
        ge=0,
        description=(
            "可选字段，当前暂不使用。source 原始内容中的 0-based 起始字符 offset。"
            "当前 adapter 会做 normalize/snippet extraction，无法可靠回推 offset；"
            "未来 docs/web extraction 如果保留 raw content offset，可填充该字段。"
        ),
    )
    char_end: int | None = Field(
        default=None,
        ge=0,
        description=(
            "可选字段，当前暂不使用。source 原始内容中的 0-based 结束字符 offset，"
            "Python slice 风格，不包含该位置。当前 adapter 会做 normalize/snippet extraction，"
            "无法可靠回推 offset；未来 docs/web extraction 如果保留 raw content offset，可填充该字段。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。span-specific 扩展定位信息，例如 chunk_index、anchor、"
            "heading_path、pdf_page_label、provider span id。用于承接尚未标准化、"
            "但确实属于片段定位的信息。"
        ),
    )

    @model_validator(mode="after")
    def _validate_ranges(self) -> "SourceEvidenceSpan":
        if self.line_start is not None and self.line_end is not None:
            if self.line_end < self.line_start:
                raise ValueError("line_end must be greater than or equal to line_start.")
        if self.char_start is not None and self.char_end is not None:
            if self.char_end < self.char_start:
                raise ValueError("char_end must be greater than or equal to char_start.")
        return self
