"""llms.txt-backed docs search adapter implementation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.adapters.docs_search.contracts.docs_search_client_protocol import (
    DocsSearchClientProtocol,
)
from app.adapters.docs_search.llms_txt_docs_search_client_config import (
    LlmsTxtDocsSearchClientConfig,
    LlmsTxtDocsSourceConfig,
)
from app.adapters.docs_search.llms_txt_docs_search_client_error import (
    LlmsTxtDocsSearchClientError,
)
from app.domain.models import (
    DocsSearchQuery,
    DocsSearchResponse,
    DocsSearchResult,
    RetrievalSourceSummary,
    SourceEvidenceSpan,
    SourceReference,
)

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)(?::\s*(.*))?")
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*")


@dataclass(frozen=True)
class _ManifestEntry:
    # llms.txt 中声明的页面标题，作为结果展示和全文抓取的语义标签。
    title: str
    # 页面绝对 URL，是构造 SourceReference 与抓取正文的稳定定位地址。
    url: str
    # 清单提供的可选页面摘要；缺失时为 None。
    summary: str | None
    # 此页面所属 docs 子来源类型，例如 openai_api。
    sub_source_type: str
    # 清单条目所在的可选章节名，供结果 metadata 和展示使用。
    section: str | None


@dataclass(frozen=True)
class _ScoredEntry:
    # 已解析的 llms.txt 清单条目。
    entry: _ManifestEntry
    # adapter 依据 query token 计算的内部相关性分数，仅用于本次排序。
    score: float


class LlmsTxtDocsSearchClient(DocsSearchClientProtocol):
    """Search configured official documentation sources exposed through llms.txt."""

    def __init__(
        self,
        config: LlmsTxtDocsSearchClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or LlmsTxtDocsSearchClientConfig.from_env()
        self._http_client = http_client

    async def search_docs(self, query: DocsSearchQuery) -> DocsSearchResponse:
        """Search configured llms.txt docs sources and return normalized snippets."""

        normalized_query = self._normalize_query(query)
        tokens = self._tokens(
            " ".join(
                value
                for value in [normalized_query.query_text, normalized_query.target_problem]
                if value
            )
        )
        entries, dropped_item_count, searched_sub_source_types = await self._load_entries(
            normalized_query
        )
        scored_entries = self._score_entries(entries, tokens)
        top_scored_entries = scored_entries[: normalized_query.limit]
        results = await self._build_results(top_scored_entries, tokens)

        return DocsSearchResponse(
            results=results,
            dropped_item_count=dropped_item_count,
            source_summary=RetrievalSourceSummary(
                normalized_count=len(results),
                metadata={
                    "searched_sub_source_types": searched_sub_source_types,
                },
            ),
        )

    def _normalize_query(self, query: DocsSearchQuery) -> DocsSearchQuery:
        query_text = query.query_text.strip()
        if not query_text:
            raise LlmsTxtDocsSearchClientError("Docs search query_text must not be empty.")
        if query.limit <= 0:
            raise LlmsTxtDocsSearchClientError("Docs search limit must be greater than zero.")
        if query.limit > self._config.max_limit:
            raise LlmsTxtDocsSearchClientError(
                f"Docs search limit must not exceed {self._config.max_limit}."
            )
        return DocsSearchQuery(
            query_text=query_text,
            target_problem=(query.target_problem or "").strip() or None,
            limit=query.limit or self._config.default_limit,
            freshness_requirement=(query.freshness_requirement or "").strip() or None,
            breadth=(query.breadth or "").strip() or None,
            sub_source_types=[
                source.strip() for source in query.sub_source_types if source.strip()
            ],
        )

    async def _load_entries(
        self,
        query: DocsSearchQuery,
    ) -> tuple[list[_ManifestEntry], int, list[str]]:
        selected_sub_source_configs = self._select_sub_source_configs(
            query.sub_source_types
        )
        entries: list[_ManifestEntry] = []
        dropped_item_count = 0

        for sub_source_config in selected_sub_source_configs:
            manifest_text = await self._get_text(sub_source_config.llms_txt_url)
            parsed_entries, dropped_count = self._parse_manifest(
                sub_source_config,
                manifest_text,
            )
            entries.extend(parsed_entries)
            dropped_item_count += dropped_count
        return (
            entries,
            dropped_item_count,
            [
                sub_source_config.sub_source_type
                for sub_source_config in selected_sub_source_configs
            ],
        )

    def _select_sub_source_configs(
        self,
        sub_source_types: list[str],
    ) -> list[LlmsTxtDocsSourceConfig]:
        if not self._config.sources:
            raise LlmsTxtDocsSearchClientError("At least one docs search source is required.")
        if not sub_source_types:
            return self._config.sources

        source_configs_by_sub_source_type = {
            source_config.sub_source_type: source_config
            for source_config in self._config.sources
        }
        missing = [
            sub_source_type
            for sub_source_type in sub_source_types
            if sub_source_type not in source_configs_by_sub_source_type
        ]
        if missing:
            raise LlmsTxtDocsSearchClientError(
                f"Unknown docs search sub_source_types: {', '.join(missing)}."
            )
        return [
            source_configs_by_sub_source_type[sub_source_type]
            for sub_source_type in sub_source_types
        ]

    async def _get_text(self, url: str) -> str:
        try:
            if self._http_client is not None:
                response = await self._http_client.get(url)
            else:
                async with httpx.AsyncClient(
                    timeout=self._config.timeout_seconds,
                    follow_redirects=True,
                ) as client:
                    response = await client.get(url)
        except httpx.TimeoutException as exc:
            raise LlmsTxtDocsSearchClientError(f"Docs search request timed out: {url}") from exc
        except httpx.RequestError as exc:
            raise LlmsTxtDocsSearchClientError(
                f"Docs search request failed for {url}: {exc}"
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            raise LlmsTxtDocsSearchClientError(
                f"Docs search request failed for {url} with status {response.status_code}."
            )
        return response.text

    def _parse_manifest(
        self,
        sub_source_config: LlmsTxtDocsSourceConfig,
        manifest_text: str,
    ) -> tuple[list[_ManifestEntry], int]:
        entries: list[_ManifestEntry] = []
        dropped_item_count = 0
        current_section: str | None = None

        for raw_line in manifest_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                current_section = line.lstrip("#").strip() or None
                continue

            match = LINK_PATTERN.search(line)
            if not match:
                if line.startswith(("-", "*")):
                    dropped_item_count += 1
                continue

            title = self._normalize_text(match.group(1))
            raw_url = match.group(2).strip()
            summary = self._normalize_text(match.group(3))
            url = urljoin(sub_source_config.llms_txt_url, raw_url)
            if not title or not url or not self._url_allowed(sub_source_config, url):
                dropped_item_count += 1
                continue

            entries.append(
                _ManifestEntry(
                    title=title,
                    url=url,
                    summary=summary,
                    sub_source_type=sub_source_config.sub_source_type,
                    section=current_section,
                )
            )
        return entries, dropped_item_count

    def _url_allowed(self, source: LlmsTxtDocsSourceConfig, url: str) -> bool:
        if not source.allowed_url_prefixes:
            return True
        return any(url.startswith(prefix) for prefix in source.allowed_url_prefixes)

    def _score_entries(
        self,
        entries: list[_ManifestEntry],
        query_tokens: set[str],
    ) -> list[_ScoredEntry]:
        scored: list[_ScoredEntry] = []
        for entry in entries:
            title_tokens = self._tokens(entry.title)
            summary_tokens = self._tokens(entry.summary or "")
            section_tokens = self._tokens(entry.section or "")

            score = 0.0
            score += 3.0 * len(query_tokens & title_tokens)
            score += 1.5 * len(query_tokens & summary_tokens)
            score += 1.0 * len(query_tokens & section_tokens)
            score += self._phrase_score(entry, query_tokens)
            if score > 0:
                scored.append(_ScoredEntry(entry=entry, score=score))

        return sorted(scored, key=lambda item: (-item.score, item.entry.title.lower()))

    def _phrase_score(self, entry: _ManifestEntry, query_tokens: set[str]) -> float:
        haystack = " ".join(
            part for part in [entry.title, entry.summary, entry.section] if part
        ).lower()
        return sum(0.5 for token in query_tokens if token in haystack)

    async def _build_results(
        self,
        scored_entries: list[_ScoredEntry],
        query_tokens: set[str],
    ) -> list[DocsSearchResult]:
        results: list[DocsSearchResult] = []
        fetch_count = min(self._config.fetch_top_pages, len(scored_entries))

        for index, scored_entry in enumerate(scored_entries):
            page_text: str | None = None
            fetch_error: str | None = None
            if index < fetch_count:
                try:
                    page_text = await self._get_text(scored_entry.entry.url)
                except LlmsTxtDocsSearchClientError as exc:
                    fetch_error = str(exc)

            content = self._snippet_for_entry(scored_entry.entry, page_text, query_tokens)
            if not content:
                continue

            metadata = {
                "rank": index + 1,
                "manifest_summary": scored_entry.entry.summary,
            }
            if fetch_error:
                metadata["page_fetch_error"] = fetch_error

            item_id = self._item_id(scored_entry.entry)
            source_reference = SourceReference(
                source_type="document",
                sub_source_type=scored_entry.entry.sub_source_type,
                source_id=item_id,
                source_id_type="docs_entry_id",
                source_url=scored_entry.entry.url,
                title=scored_entry.entry.title,
                publisher=None,
                evidence_span=SourceEvidenceSpan(section=scored_entry.entry.section)
                if scored_entry.entry.section
                else None,
                citation_text=scored_entry.entry.title,
            )

            results.append(
                DocsSearchResult(
                    item_id=item_id,
                    title=scored_entry.entry.title,
                    content=content,
                    source_reference=source_reference,
                    score=scored_entry.score,
                    metadata=metadata,
                )
            )
        return results

    def _snippet_for_entry(
        self,
        entry: _ManifestEntry,
        page_text: str | None,
        query_tokens: set[str],
    ) -> str | None:
        if page_text:
            page_text = page_text[: self._config.max_page_chars]
            snippet = self._extract_page_snippet(page_text, query_tokens)
            if snippet:
                return snippet
        return entry.summary or entry.title

    def _extract_page_snippet(self, page_text: str, query_tokens: set[str]) -> str | None:
        paragraphs = [
            self._normalize_text(paragraph)
            for paragraph in re.split(r"\n\s*\n", page_text)
        ]
        candidates = [paragraph for paragraph in paragraphs if paragraph]
        if not candidates:
            return None

        def score(paragraph: str) -> tuple[int, int]:
            tokens = self._tokens(paragraph)
            return (len(tokens & query_tokens), -len(paragraph))

        best = max(candidates, key=score)
        if score(best)[0] == 0:
            return candidates[0]
        return best

    def _item_id(self, entry: _ManifestEntry) -> str:
        digest = hashlib.sha256(
            f"{entry.sub_source_type}:{entry.url}".encode("utf-8")
        ).hexdigest()
        return f"docs_{digest[:16]}"

    def _tokens(self, value: str) -> set[str]:
        return {
            token.lower()
            for token in TOKEN_PATTERN.findall(value)
            if len(token) > 1
        }

    def _normalize_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None
