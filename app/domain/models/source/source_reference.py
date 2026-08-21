"""Source reference model."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.utils.text import strip_optional_string
from app.domain.models.source.source_evidence_span import SourceEvidenceSpan


class SourceReference(BaseModel):
    """表示 memory、knowledge 或 retrieved material 所依赖的原始 evidence 来源。"""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    source_type: str = Field(
        min_length=1,
        description=(
            "必填字段。原始来源类型，例如 web_page、paper、document、conversation、"
            "run_output、code_repo。当前 web_search/web_content_fetch 可填 web_page，"
            "paper_search/paper_content_fetch 可填 paper，docs_search 可填 document。"
            "不使用 enum，以保持未来来源类型可扩展。"
        ),
    )
    sub_source_type: str | None = Field(
        default=None,
        description=(
            "可选字段。source_type 之下的子来源类型或子来源标识，例如 docs_search 中的 "
            "openai_api、anthropic_api、claude_code。当前主要用于区分同一大类来源下的"
            "具体子来源；本轮 docs_search adapter 会填充该字段，其它 adapter 当前可为空。"
        ),
    )
    source_id: str | None = Field(
        default=None,
        description=(
            "可选字段。来源在其命名空间内的稳定逻辑 ID，例如 arxiv_id、doi、"
            "docs entry id、run id、conversation id、repo path、file path。"
            "paper_search 可填 arxiv_id 或 paper_id；web_search 可填 URL hash/item_id；"
            "当来源只有 URL、没有稳定 ID 时可为空。"
        ),
    )
    source_id_type: str | None = Field(
        default=None,
        description=(
            "可选字段，但依赖 source_id。source_id 的命名空间或 ID 类型，例如 arxiv_id、"
            "doi、semantic_scholar_id、openalex_id、docs_entry_id、url_sha1、run_id、"
            "conversation_id、repo_path。若填写该字段，必须同时填写 source_id；"
            "第一版不强制 source_id 非空时必须填写该字段，以兼容旧 embedded source_refs。"
        ),
    )
    source_url: str | None = Field(
        default=None,
        description=(
            "可选字段。可访问的来源 URL，例如网页 URL、docs URL、paper abstract URL、"
            "PDF URL、DOI URL。web_search/web_content_fetch 可填 url，docs_search 可填 url "
            "或 source_ref，paper_content_fetch 可填 source_url；当来源只有内部稳定 ID "
            "或非 URL 定位符时可为空。"
        ),
    )
    title: str | None = Field(
        default=None,
        description=(
            "可选字段。原始来源标题，例如网页标题、论文标题、docs 页面标题。"
            "web_search、docs_search、paper_search 通常可填；research_knowledge_memory 场景下"
            "应来自 distill 前原始 source ref，而不是 knowledge unit 标题。"
        ),
    )
    authors: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。原始来源作者列表。paper_search 可由 "
            "PaperSearchResult.authors 填充；web/docs 通常为空，除非原始 source metadata "
            "明确提供 author；research_knowledge_memory 应透传 distill 前 source_refs 中的 authors。"
            "不要用 owner_user_id、created_by 或 provider 名称伪造 authors。"
        ),
    )
    publisher: str | None = Field(
        default=None,
        description=(
            "可选字段。原始来源发布方、机构、网站或文档所属组织。docs/web 只有在语义明确时"
            "才填；不要把 retrieval provider 名称伪装成 publisher，provider 信息应放 metadata；"
            "research_knowledge_memory 应透传 distill 前 source ref 的 publisher。"
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        description=(
            "可选字段。原始 source 的发布时间或更新发布时间。web_search 和 paper_search "
            "可能可填；它不是系统检索时间，也不是 knowledge record 的 updated_at 或 last_verified_at。"
        ),
    )
    retrieved_at: datetime | None = Field(
        default=None,
        description=(
            "可选字段，当前多数 live adapters 暂不使用。系统获取或验证该 source 的时间。"
            "当前 web_search、docs_search、paper_search 等 adapter 多数暂不显式返回 retrieved_at，"
            "因此通常为空；不要用 published_at 或 knowledge updated_at 伪造。"
        ),
    )
    evidence_span: SourceEvidenceSpan | None = Field(
        default=None,
        description=(
            "可选字段。该引用指向的 source 内部证据片段位置；如果引用整个 source，则为空。"
            "当前 docs_search 可由 DocsSearchResult.section 填充 section；其它 adapter 多数暂不使用。"
        ),
    )
    citation_text: str | None = Field(
        default=None,
        description=(
            "可选字段。用于展示的短 citation label，例如论文引用、网页标题、docs section label。"
            "该字段只服务展示和解释，不应用作唯一标识。"
        ),
    )
    source_ref_id: str | None = Field(
        default=None,
        description=(
            "可选字段，当前暂不使用。未来如果 Source Reference 独立成表时使用的稳定 ID。"
            "当前没有 source reference 表，因此本轮通常保持为空。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。source-specific/provider-specific 附加信息，例如 score、rank、"
            "favicon、pdf_url、doi_url、categories、download_bytes、page_fetch_error。"
            "不要把可稳定建模的主字段长期塞在这里。"
        ),
    )

    def deduplication_key(self) -> str:
        """返回供跨阶段 SourceReference 去重使用的稳定身份键。"""

        if self.source_url:
            return f"url:{self.source_url}"
        if self.source_id:
            return f"id:{self.source_id_type or ''}:{self.source_id}"
        if self.citation_text:
            return f"citation:{self.citation_text}"
        return "json:" + json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )

    @model_validator(mode="before")
    @classmethod
    def _map_legacy_source_uri(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        normalized = dict(value)
        source_uri = normalized.pop("source_uri", None)
        if source_uri and not normalized.get("source_id") and not normalized.get("source_url"):
            source_uri_text = str(source_uri).strip()
            if source_uri_text.lower().startswith(("http://", "https://")):
                normalized["source_url"] = source_uri_text
            else:
                normalized["source_id"] = source_uri_text
        return normalized

    @field_validator(
        "source_type",
        "sub_source_type",
        "source_id",
        "source_id_type",
        "source_url",
        "title",
        "publisher",
        "citation_text",
        "source_ref_id",
        mode="before",
    )
    @classmethod
    def _strip_optional_text(cls, value: Any) -> Any:
        return strip_optional_string(value)

    @field_validator("authors", mode="before")
    @classmethod
    def _normalize_authors(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            normalized: list[str] = []
            for item in value:
                if not isinstance(item, str):
                    continue
                stripped = item.strip()
                if stripped:
                    normalized.append(stripped)
            return normalized
        return value

    @model_validator(mode="after")
    def _validate_source_identity(self) -> "SourceReference":
        if not self.source_type:
            raise ValueError("source_type must not be empty.")
        if not self.source_id and not self.source_url:
            raise ValueError("Either source_id or source_url must be provided.")
        if self.source_id_type and not self.source_id:
            raise ValueError("source_id_type requires source_id to be provided.")
        return self
