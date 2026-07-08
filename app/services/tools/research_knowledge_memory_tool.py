"""Runtime-facing tool that recalls reusable research knowledge units."""

from __future__ import annotations

from typing import Any

from app.adapters.embedding.contracts.embedding_client_protocol import EmbeddingClientProtocol
from app.adapters.memory.contracts.research_knowledge_memory_store_protocol import (
    ResearchKnowledgeMemoryStoreProtocol,
)
from app.domain.enums import AcquisitionStatus, FamilyName
from app.domain.models import (
    ResearchKnowledgeMemoryToolRequest,
    ResearchKnowledgeMemoryToolResult,
    ResearchKnowledgeRecallQuery,
    ResearchKnowledgeRecallResult,
    ResearchKnowledgeUnitRecord,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
    SourceReference,
)
from app.domain.models.retrieval import NormalizedRetrievalItem
from app.services.tools.contracts.research_knowledge_memory_tool_protocol import (
    ResearchKnowledgeMemoryToolProtocol,
)


class ResearchKnowledgeMemoryTool(ResearchKnowledgeMemoryToolProtocol):
    """Tool service that recalls reusable research knowledge from memory."""

    def __init__(
        self,
        research_knowledge_store: ResearchKnowledgeMemoryStoreProtocol,
        embedding_client: EmbeddingClientProtocol,
    ) -> None:
        self._research_knowledge_store = research_knowledge_store
        self._embedding_client = embedding_client

    async def run(
        self,
        request: ResearchKnowledgeMemoryToolRequest,
    ) -> ResearchKnowledgeMemoryToolResult:
        """Execute research knowledge recall and return normalized candidate materials."""

        normalized_request = self._normalize_request(request)
        validation_error = self._validate_request(normalized_request)
        if validation_error:
            return self._failed_result(normalized_request=normalized_request, error_info=validation_error)

        query_embedding, used_precomputed_embedding, embedding_error = (
            await self._resolve_query_embedding(normalized_request)
        )
        if embedding_error or query_embedding is None:
            return self._failed_result(
                normalized_request=normalized_request,
                error_info=embedding_error or "Failed to resolve query embedding.",
                used_query_embedding=used_precomputed_embedding,
            )

        try:
            recall_results = await self._research_knowledge_store.recall_knowledge_units(
                ResearchKnowledgeRecallQuery(
                    owner_user_id=normalized_request.owner_user_id,
                    query_embedding=query_embedding,
                    allowed_visibility_scopes=normalized_request.allowed_visibility_scopes,
                    project_scope_id=normalized_request.project_scope_id,
                    knowledge_types=normalized_request.knowledge_types,
                    topic_tags=normalized_request.topic_tags,
                    source_types=normalized_request.source_types,
                    limit=normalized_request.limit,
                )
            )
        except Exception as exc:
            return self._failed_result(
                normalized_request=normalized_request,
                error_info=str(exc),
                used_query_embedding=used_precomputed_embedding,
            )

        normalized_items, dropped_item_count = self._normalize_items(recall_results)
        if not normalized_items:
            return self._no_result(
                normalized_request=normalized_request,
                recall_result_count=len(recall_results),
                dropped_item_count=dropped_item_count,
                used_query_embedding=used_precomputed_embedding,
            )

        return self._create_result(
            normalized_request=normalized_request,
            recall_results=recall_results,
            normalized_items=normalized_items,
            dropped_item_count=dropped_item_count,
            used_precomputed_embedding=used_precomputed_embedding,
        )

    def _normalize_request(
        self,
        request: ResearchKnowledgeMemoryToolRequest,
    ) -> ResearchKnowledgeMemoryToolRequest:
        return ResearchKnowledgeMemoryToolRequest(
            owner_user_id=request.owner_user_id.strip(),
            query_text=(request.query_text or "").strip() or None,
            query_embedding=request.query_embedding,
            project_scope_id=(request.project_scope_id or "").strip() or None,
            allowed_visibility_scopes=[
                value.strip() for value in request.allowed_visibility_scopes if value.strip()
            ],
            knowledge_types=[value.strip() for value in request.knowledge_types if value.strip()],
            topic_tags=[value.strip() for value in request.topic_tags if value.strip()],
            source_types=[value.strip() for value in request.source_types if value.strip()],
            limit=request.limit,
        )

    def _validate_request(self, request: ResearchKnowledgeMemoryToolRequest) -> str | None:
        if not request.owner_user_id:
            return "owner_user_id must not be empty."
        if not request.allowed_visibility_scopes:
            return "allowed_visibility_scopes must include at least one scope."
        if not request.query_embedding and not request.query_text:
            return "Either query_embedding or query_text must be provided."
        return None

    async def _resolve_query_embedding(
        self,
        normalized_request: ResearchKnowledgeMemoryToolRequest,
    ) -> tuple[list[float] | None, bool, str | None]:
        if normalized_request.query_embedding:
            return normalized_request.query_embedding, True, None

        try:
            embedding = await self._embedding_client.embed_text(
                normalized_request.query_text or ""
            )
        except Exception as exc:
            return None, False, str(exc)
        return embedding.embedding, False, None

    def _create_result(
        self,
        *,
        normalized_request: ResearchKnowledgeMemoryToolRequest,
        recall_results: list[ResearchKnowledgeRecallResult],
        normalized_items: list[NormalizedRetrievalItem],
        dropped_item_count: int,
        used_precomputed_embedding: bool,
    ) -> ResearchKnowledgeMemoryToolResult:
        return ResearchKnowledgeMemoryToolResult(
            normalized_items=normalized_items,
            acquisition_status=AcquisitionStatus.PARTIAL_SUCCESS if dropped_item_count > 0 else AcquisitionStatus.SUCCESS,
            dropped_item_count=dropped_item_count,
            source_summary=RetrievalSourceSummary(
                selected_family=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                normalized_count=len(normalized_items),
            ),
            execution_summary=RetrievalExecutionSummary(
                normalized_count=len(normalized_items),
                dropped_item_count=dropped_item_count,
                metrics={"recall_result_count": len(recall_results)},
                observability={"used_precomputed_embedding": used_precomputed_embedding},
            ),
            retrieval_trace=RetrievalTrace(
                selected_family=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                returned_refs=[self._source_ref(item) for item in normalized_items],
                context={
                    "query_text": normalized_request.query_text,
                    "used_query_embedding": used_precomputed_embedding,
                    "project_scope_id": normalized_request.project_scope_id,
                    "allowed_visibility_scopes": normalized_request.allowed_visibility_scopes,
                    "knowledge_types": normalized_request.knowledge_types,
                    "topic_tags": normalized_request.topic_tags,
                    "source_types": normalized_request.source_types,
                },
            ),
            error_info=None,
        )

    def _normalize_items(
        self,
        results: list[ResearchKnowledgeRecallResult],
    ) -> tuple[list[NormalizedRetrievalItem], int]:
        normalized_items: list[NormalizedRetrievalItem] = []
        dropped_item_count = 0

        for result in results:
            try:
                unit = result.unit
                normalized_items.append(
                    NormalizedRetrievalItem(
                        item_id=unit.knowledge_id,
                        source_family=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                        source_references=self._source_references(unit),
                        content=unit.summary,
                        content_type="knowledge_summary",
                        metadata={
                            "title": unit.title,
                            "knowledge_type": unit.knowledge_type,
                            "topic_tags": unit.topic_tags,
                            "source_refs": [
                                source_ref.model_dump(mode="json")
                                for source_ref in unit.source_refs
                            ],
                            "source_type": unit.source_type,
                            "project_scope_id": unit.project_scope_id,
                            "visibility_scope": unit.visibility_scope,
                            "visibility_scope_effective": unit.visibility_scope_effective,
                            "confidence": unit.confidence,
                            "status": unit.status,
                            "freshness_sensitivity": unit.freshness_sensitivity,
                            "freshness_status": unit.freshness_status,
                            "last_verified_at": (
                                unit.last_verified_at.isoformat() if unit.last_verified_at else None
                            ),
                            "updated_at": unit.updated_at.isoformat() if unit.updated_at else None,
                            "relevance_score": result.relevance_score,
                        },
                    )
                )
            except Exception:
                dropped_item_count += 1
        return normalized_items, dropped_item_count

    def _source_references(self, unit: ResearchKnowledgeUnitRecord) -> list[SourceReference]:
        if unit.source_refs:
            return [
                reference.model_copy(
                    update={
                        "metadata": {
                            **reference.metadata,
                            "knowledge_id": unit.knowledge_id,
                            "knowledge_type": unit.knowledge_type,
                        }
                    }
                )
                for reference in unit.source_refs
            ]

        if unit.derived_from_run_id:
            return [
                SourceReference(
                    source_type="run_output",
                    source_id=unit.derived_from_run_id,
                    source_id_type="run_id",
                    metadata={
                        "knowledge_id": unit.knowledge_id,
                        "knowledge_type": unit.knowledge_type,
                    },
                )
            ]

        if unit.derived_from_session_id:
            return [
                SourceReference(
                    source_type="conversation",
                    source_id=unit.derived_from_session_id,
                    source_id_type="session_id",
                    metadata={
                        "knowledge_id": unit.knowledge_id,
                        "knowledge_type": unit.knowledge_type,
                    },
                )
            ]

        raise ValueError(
            "Research knowledge unit does not include a usable original source reference."
        )

    def _source_ref(self, item: NormalizedRetrievalItem) -> str:
        source_reference = item.source_references[0]
        return (
            source_reference.source_url
            or source_reference.source_id
            or item.item_id
        )

    def _failed_result(
        self,
        *,
        normalized_request: ResearchKnowledgeMemoryToolRequest,
        error_info: str,
        used_query_embedding: bool | None = None,
    ) -> ResearchKnowledgeMemoryToolResult:
        return ResearchKnowledgeMemoryToolResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.FAILED,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
                selected_family=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                normalized_count=0,
            ),
            execution_summary=RetrievalExecutionSummary(
                normalized_count=0,
                dropped_item_count=0,
                metrics={"recall_result_count": 0},
                observability={"used_precomputed_embedding": bool(used_query_embedding)},
            ),
            retrieval_trace=RetrievalTrace(
                selected_family=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                returned_refs=[],
                errors={"recall_error": error_info},
                context={
                    "query_text": normalized_request.query_text,
                    "used_query_embedding": bool(used_query_embedding),
                    "project_scope_id": normalized_request.project_scope_id,
                    "allowed_visibility_scopes": normalized_request.allowed_visibility_scopes,
                    "knowledge_types": normalized_request.knowledge_types,
                    "topic_tags": normalized_request.topic_tags,
                    "source_types": normalized_request.source_types,
                },
            ),
            error_info=error_info,
        )

    def _no_result(
        self,
        *,
        normalized_request: ResearchKnowledgeMemoryToolRequest,
        recall_result_count: int,
        dropped_item_count: int,
        used_query_embedding: bool,
    ) -> ResearchKnowledgeMemoryToolResult:
        return ResearchKnowledgeMemoryToolResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.NO_RESULT,
            dropped_item_count=dropped_item_count,
            source_summary=RetrievalSourceSummary(
                selected_family=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                normalized_count=0,
            ),
            execution_summary=RetrievalExecutionSummary(
                normalized_count=0,
                dropped_item_count=dropped_item_count,
                metrics={"recall_result_count": recall_result_count},
                observability={"used_precomputed_embedding": used_query_embedding},
            ),
            retrieval_trace=RetrievalTrace(
                selected_family=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                returned_refs=[],
                context={
                    "query_text": normalized_request.query_text,
                    "used_query_embedding": used_query_embedding,
                    "project_scope_id": normalized_request.project_scope_id,
                    "allowed_visibility_scopes": normalized_request.allowed_visibility_scopes,
                    "knowledge_types": normalized_request.knowledge_types,
                    "topic_tags": normalized_request.topic_tags,
                    "source_types": normalized_request.source_types,
                },
            ),
            error_info=None,
        )
