"""research_knowledge_memory tool tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.domain.models import (
    EmbeddingResult,
    ResearchKnowledgeMemoryToolRequest,
    ResearchKnowledgeRecallResult,
    ResearchKnowledgeUnitRecord,
    SourceReference,
)
from app.services.tools.research_knowledge_memory_tool import ResearchKnowledgeMemoryTool


class FakeEmbeddingClient:
    def __init__(self, response: EmbeddingResult | Exception) -> None:
        self.response = response
        self.last_text: str | None = None

    async def embed_text(self, text: str):
        self.last_text = text
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def embed_texts(self, texts: list[str]):
        raise NotImplementedError


class FakeResearchKnowledgeStore:
    def __init__(self, response: list[ResearchKnowledgeRecallResult] | Exception) -> None:
        self.response = response
        self.last_query = None

    async def recall_knowledge_units(self, query):
        self.last_query = query
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _embedding_result(values: list[float]) -> EmbeddingResult:
    return EmbeddingResult(
        text_index=0,
        embedding=values,
        model="embedding-model",
        dimensions=len(values),
    )


UNIT = ResearchKnowledgeUnitRecord(
    knowledge_id="knowledge-1",
    owner_user_id="user-1",
    project_scope_id="project-1",
    visibility_scope="project",
    visibility_scope_effective="project",
    title="PostgreSQL + pgvector governance",
    summary="PostgreSQL + pgvector keeps governance fields and vectors together.",
    knowledge_type="engineering_observation",
    topic_tags=["postgresql", "pgvector"],
    confidence=0.88,
    source_refs=[
        SourceReference(
            source_type="web_page",
            source_url="https://example.test/pgvector",
        ),
        SourceReference(
            source_type="paper",
            source_id="2501.00001",
            source_id_type="arxiv_id",
        )
    ],
    source_type="web_page",
    derived_from_session_id="session-1",
    derived_from_run_id="run-1",
    created_by="llm",
    status="active",
    created_at=datetime(2026, 6, 3, 10, 0, tzinfo=UTC),
    updated_at=datetime(2026, 6, 3, 10, 5, tzinfo=UTC),
    archived_at=None,
    pruned_at=None,
    freshness_sensitivity="medium",
    freshness_status="fresh",
    last_verified_at=datetime(2026, 6, 3, 9, 30, tzinfo=UTC),
    freshness_checked_at=datetime(2026, 6, 3, 9, 45, tzinfo=UTC),
    staleness_reason=None,
    dedupe_key="postgres-pgvector-governed-knowledge",
    canonical_knowledge_id="knowledge-1",
    is_canonical=True,
    merged_into_id=None,
    embedding_text="PostgreSQL + pgvector governance\nPostgreSQL + pgvector keeps governance fields and vectors together.",
    embedding_vector=[0.1, 0.2, 0.3],
    embedding_model="embedding-model",
    embedding_version="v1",
)


def test_run_prefers_precomputed_embedding() -> None:
    embedding_client = FakeEmbeddingClient(_embedding_result([9.0]))
    store = FakeResearchKnowledgeStore(
        [ResearchKnowledgeRecallResult(unit=UNIT, relevance_score=0.91)]
    )
    tool = ResearchKnowledgeMemoryTool(store, embedding_client)

    result = asyncio.run(
        tool.run(
            ResearchKnowledgeMemoryToolRequest(
                owner_user_id="user-1",
                query_text="should not be embedded",
                query_embedding=[0.1, 0.2, 0.3],
                project_scope_id="project-1",
                allowed_visibility_scopes=["project"],
                knowledge_types=["engineering_observation"],
                topic_tags=["pgvector"],
                source_types=["web_page"],
                limit=3,
            )
        )
    )

    assert embedding_client.last_text is None
    assert store.last_query is not None
    assert store.last_query.query_embedding == [0.1, 0.2, 0.3]
    assert store.last_query.project_scope_id == "project-1"
    assert store.last_query.allowed_visibility_scopes == ["project"]
    assert store.last_query.knowledge_types == ["engineering_observation"]
    assert store.last_query.topic_tags == ["pgvector"]
    assert store.last_query.source_types == ["web_page"]
    assert store.last_query.limit == 3
    assert result.acquisition_status == "success"
    assert result.execution_summary["used_precomputed_embedding"] is True


def test_run_uses_query_text_when_embedding_missing() -> None:
    embedding_client = FakeEmbeddingClient(_embedding_result([0.4, 0.5]))
    store = FakeResearchKnowledgeStore(
        [ResearchKnowledgeRecallResult(unit=UNIT, relevance_score=0.91)]
    )
    tool = ResearchKnowledgeMemoryTool(store, embedding_client)

    result = asyncio.run(
        tool.run(
            ResearchKnowledgeMemoryToolRequest(
                owner_user_id="user-1",
                query_text=" postgres ",
            )
        )
    )

    assert embedding_client.last_text == "postgres"
    assert store.last_query is not None
    assert store.last_query.query_embedding == [0.4, 0.5]
    assert result.acquisition_status == "success"
    assert result.execution_summary["used_precomputed_embedding"] is False


def test_run_normalizes_recalled_items() -> None:
    tool = ResearchKnowledgeMemoryTool(
        FakeResearchKnowledgeStore([ResearchKnowledgeRecallResult(unit=UNIT, relevance_score=0.91)]),
        FakeEmbeddingClient(_embedding_result([0.4])),
    )

    result = asyncio.run(
        tool.run(ResearchKnowledgeMemoryToolRequest(owner_user_id="user-1", query_text="postgres"))
    )

    assert len(result.normalized_items) == 1
    item = result.normalized_items[0]
    assert item["item_id"] == "knowledge-1"
    assert item["source_family"] == "research_knowledge_recall"
    assert len(item["source_references"]) == 2
    assert item["source_references"][0].source_type == "web_page"
    assert item["source_references"][0].source_url == "https://example.test/pgvector"
    assert item["source_references"][0].metadata["knowledge_id"] == "knowledge-1"
    assert item["source_references"][1].source_type == "paper"
    assert item["source_references"][1].source_id == "2501.00001"
    assert item["source_references"][1].metadata["knowledge_id"] == "knowledge-1"
    assert "source_type" not in item.model_dump()
    assert "source_ref" not in item.model_dump()
    assert "source_reference" not in item.model_dump()
    assert item["content"] == UNIT.summary
    assert item["content_type"] == "knowledge_summary"
    assert item["metadata"]["title"] == UNIT.title
    assert item["metadata"]["relevance_score"] == 0.91
    assert item["metadata"]["source_refs"][0]["source_url"] == "https://example.test/pgvector"
    assert item["metadata"]["source_refs"][1]["source_id"] == "2501.00001"
    assert result.retrieval_trace["returned_refs"] == ["https://example.test/pgvector"]


def test_run_returns_no_result_for_empty_recall() -> None:
    tool = ResearchKnowledgeMemoryTool(
        FakeResearchKnowledgeStore([]),
        FakeEmbeddingClient(_embedding_result([0.4])),
    )

    result = asyncio.run(
        tool.run(ResearchKnowledgeMemoryToolRequest(owner_user_id="user-1", query_text="postgres"))
    )

    assert result.acquisition_status == "no_result"
    assert result.normalized_items == []


def test_run_returns_failed_when_embedding_raises() -> None:
    tool = ResearchKnowledgeMemoryTool(
        FakeResearchKnowledgeStore([]),
        FakeEmbeddingClient(RuntimeError("embed boom")),
    )

    result = asyncio.run(
        tool.run(ResearchKnowledgeMemoryToolRequest(owner_user_id="user-1", query_text="postgres"))
    )

    assert result.acquisition_status == "failed"
    assert result.error_info == "embed boom"


def test_run_returns_failed_when_recall_raises() -> None:
    tool = ResearchKnowledgeMemoryTool(
        FakeResearchKnowledgeStore(RuntimeError("recall boom")),
        FakeEmbeddingClient(_embedding_result([0.4])),
    )

    result = asyncio.run(
        tool.run(ResearchKnowledgeMemoryToolRequest(owner_user_id="user-1", query_text="postgres"))
    )

    assert result.acquisition_status == "failed"
    assert result.error_info == "recall boom"


def test_run_returns_failed_for_missing_query_input() -> None:
    tool = ResearchKnowledgeMemoryTool(
        FakeResearchKnowledgeStore([]),
        FakeEmbeddingClient(_embedding_result([0.4])),
    )

    result = asyncio.run(
        tool.run(
            ResearchKnowledgeMemoryToolRequest(
                owner_user_id="user-1",
                query_text=None,
                query_embedding=None,
            )
        )
    )

    assert result.acquisition_status == "failed"
    assert "Either query_embedding or query_text" in (result.error_info or "")


def test_run_returns_failed_for_empty_visibility_scopes_after_normalization() -> None:
    tool = ResearchKnowledgeMemoryTool(
        FakeResearchKnowledgeStore([]),
        FakeEmbeddingClient(_embedding_result([0.4])),
    )

    result = asyncio.run(
        tool.run(
            ResearchKnowledgeMemoryToolRequest(
                owner_user_id="user-1",
                query_text="postgres",
                allowed_visibility_scopes=["", "   "],
            )
        )
    )

    assert result.acquisition_status == "failed"
    assert "allowed_visibility_scopes" in (result.error_info or "")


def test_run_drops_unmappable_results_and_returns_partial_success() -> None:
    class BrokenResult:
        unit = object()
        relevance_score = 0.1

    tool = ResearchKnowledgeMemoryTool(
        FakeResearchKnowledgeStore([
            ResearchKnowledgeRecallResult(unit=UNIT, relevance_score=0.91),
            BrokenResult(),
        ]),
        FakeEmbeddingClient(_embedding_result([0.4])),
    )

    result = asyncio.run(
        tool.run(ResearchKnowledgeMemoryToolRequest(owner_user_id="user-1", query_text="postgres"))
    )

    assert result.acquisition_status == "partial_success"
    assert len(result.normalized_items) == 1
    assert result.dropped_item_count == 1


def test_run_returns_no_result_when_all_results_are_dropped() -> None:
    class BrokenResult:
        unit = object()
        relevance_score = 0.1

    tool = ResearchKnowledgeMemoryTool(
        FakeResearchKnowledgeStore([BrokenResult()]),
        FakeEmbeddingClient(_embedding_result([0.4])),
    )

    result = asyncio.run(
        tool.run(ResearchKnowledgeMemoryToolRequest(owner_user_id="user-1", query_text="postgres"))
    )

    assert result.acquisition_status == "no_result"
    assert result.dropped_item_count == 1
