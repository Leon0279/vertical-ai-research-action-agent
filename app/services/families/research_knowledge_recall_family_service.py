"""Family-level service for research knowledge recall retrieval execution."""

from __future__ import annotations

from app.domain.enums import AcquisitionStatus, FamilyName
from app.domain.models import (
    ResearchKnowledgeMemoryToolRequest,
    ResearchKnowledgeMemoryToolResult,
    ResearchKnowledgeRecallFamilyRequest,
    ResearchKnowledgeRecallFamilyResult,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)
from app.services.families.contracts.research_knowledge_recall_family_service_protocol import (
    ResearchKnowledgeRecallFamilyServiceProtocol,
)
from app.services.families._selection import select_preferred_or_default_tool
from app.services.tools.contracts.research_knowledge_memory_tool_protocol import (
    ResearchKnowledgeMemoryToolProtocol,
)


class ResearchKnowledgeRecallFamilyService(ResearchKnowledgeRecallFamilyServiceProtocol):
    """负责处理研究知识召回检索族相关业务逻辑的服务。

Resolve a research_knowledge_recall family request to a concrete recall tool."""

    _FAMILY_NAME = FamilyName.RESEARCH_KNOWLEDGE_RECALL
    _DEFAULT_TOOL_ID = "research_knowledge_memory_v1"

    def __init__(
        self,
        research_knowledge_memory_tool: ResearchKnowledgeMemoryToolProtocol | None,
    ) -> None:
        self._tool_registry: dict[str, ResearchKnowledgeMemoryToolProtocol] = {}
        if research_knowledge_memory_tool is not None:
            self._tool_registry[self._DEFAULT_TOOL_ID] = research_knowledge_memory_tool

    async def run(
        self,
        request: ResearchKnowledgeRecallFamilyRequest,
    ) -> ResearchKnowledgeRecallFamilyResult:
        """Select a research_knowledge_recall tool and return a family-level result."""

        normalized_request = self._normalize_request(request)
        candidate_tools = list(self._tool_registry)

        if not candidate_tools:
            return self._failed_result(
                normalized_request=normalized_request,
                candidate_tools=[],
                selected_tool=None,
                error_info="No available tools registered for research_knowledge_recall family.",
            )

        selected_tool = select_preferred_or_default_tool(
            normalized_request.preferred_tool,
            self._DEFAULT_TOOL_ID,
            candidate_tools,
        )
        if selected_tool is None:
            return self._failed_result(
                normalized_request=normalized_request,
                candidate_tools=candidate_tools,
                selected_tool=None,
                error_info=(
                    f"Preferred tool '{normalized_request.preferred_tool}' is not available in "
                    "research_knowledge_recall family."
                ),
            )

        tool = self._tool_registry[selected_tool]
        tool_result = await tool.run(
            ResearchKnowledgeMemoryToolRequest(
                owner_user_id=normalized_request.owner_user_id,
                query_text=normalized_request.query_text,
                query_embedding=normalized_request.query_embedding,
                project_scope_id=normalized_request.project_scope_id,
                allowed_visibility_scopes=normalized_request.allowed_visibility_scopes,
                knowledge_types=normalized_request.knowledge_types,
                topic_tags=normalized_request.topic_tags,
                source_types=normalized_request.source_types,
                limit=normalized_request.limit,
            )
        )
        return self._wrap_tool_result(
            normalized_request=normalized_request,
            candidate_tools=candidate_tools,
            selected_tool=selected_tool,
            tool_result=tool_result,
        )

    def _normalize_request(
        self,
        request: ResearchKnowledgeRecallFamilyRequest,
    ) -> ResearchKnowledgeRecallFamilyRequest:
        return ResearchKnowledgeRecallFamilyRequest(
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
            preferred_tool=(request.preferred_tool or "").strip() or None,
        )

    def _wrap_tool_result(
        self,
        *,
        normalized_request: ResearchKnowledgeRecallFamilyRequest,
        candidate_tools: list[str],
        selected_tool: str,
        tool_result: ResearchKnowledgeMemoryToolResult,
    ) -> ResearchKnowledgeRecallFamilyResult:
        source_summary = tool_result.source_summary.model_copy(
            update={
                "selected_family": self._FAMILY_NAME,
                "selected_tool": selected_tool,
            }
        )

        execution_summary = tool_result.execution_summary.model_copy(
            update={
                "metrics": {
                    **tool_result.execution_summary.metrics,
                    "candidate_tool_count": len(candidate_tools),
                },
                "observability": {
                    **tool_result.execution_summary.observability,
                    "preferred_tool_requested": normalized_request.preferred_tool,
                },
            }
        )

        retrieval_trace = tool_result.retrieval_trace.model_copy(
            update={
                "selected_family": self._FAMILY_NAME,
                "selected_tool": selected_tool,
                "context": {
                    **tool_result.retrieval_trace.context,
                    "candidate_tools": candidate_tools,
                    "preferred_tool": normalized_request.preferred_tool,
                },
            }
        )

        return ResearchKnowledgeRecallFamilyResult(
            normalized_items=tool_result.normalized_items,
            acquisition_status=tool_result.acquisition_status,
            dropped_item_count=tool_result.dropped_item_count,
            source_summary=source_summary,
            execution_summary=execution_summary,
            retrieval_trace=retrieval_trace,
            error_info=tool_result.error_info,
            selected_family=self._FAMILY_NAME,
            candidate_tools=candidate_tools,
            selected_tool=selected_tool,
        )

    def _failed_result(
        self,
        *,
        normalized_request: ResearchKnowledgeRecallFamilyRequest,
        candidate_tools: list[str],
        selected_tool: str | None,
        error_info: str,
    ) -> ResearchKnowledgeRecallFamilyResult:
        return ResearchKnowledgeRecallFamilyResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.FAILED,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
                selected_family=self._FAMILY_NAME,
                selected_tool=selected_tool,
                normalized_count=0,
            ),
            execution_summary=RetrievalExecutionSummary(
                normalized_count=0,
                metrics={"candidate_tool_count": len(candidate_tools)},
                observability={"preferred_tool_requested": normalized_request.preferred_tool},
            ),
            retrieval_trace=RetrievalTrace(
                selected_family=self._FAMILY_NAME,
                selected_tool=selected_tool,
                context={
                    "candidate_tools": candidate_tools,
                    "preferred_tool": normalized_request.preferred_tool,
                    "owner_user_id": normalized_request.owner_user_id,
                    "query_text": normalized_request.query_text,
                    "project_scope_id": normalized_request.project_scope_id,
                    "allowed_visibility_scopes": normalized_request.allowed_visibility_scopes,
                    "knowledge_types": normalized_request.knowledge_types,
                    "topic_tags": normalized_request.topic_tags,
                    "source_types": normalized_request.source_types,
                },
                errors={"family_error": error_info},
            ),
            error_info=error_info,
            selected_family=self._FAMILY_NAME,
            candidate_tools=candidate_tools,
            selected_tool=selected_tool,
        )
