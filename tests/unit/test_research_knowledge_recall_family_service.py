"""research_knowledge_recall family service tests."""

from __future__ import annotations

import asyncio

from app.domain.models import (
    ResearchKnowledgeMemoryToolResult,
    ResearchKnowledgeRecallFamilyRequest,
)
from app.services.families.research_knowledge_recall_family_service import (
    ResearchKnowledgeRecallFamilyService,
)


class FakeResearchKnowledgeMemoryTool:
    def __init__(self, response: ResearchKnowledgeMemoryToolResult) -> None:
        self.response = response
        self.last_request = None

    async def run(self, request):
        self.last_request = request
        return self.response


SUCCESS_RESULT = ResearchKnowledgeMemoryToolResult(
    normalized_items=[
        {
            "item_id": "knowledge-1",
            "source_family": "research_knowledge_recall",
            "source_type": "knowledge_unit",
            "source_ref": "knowledge-1",
            "content": "Governed knowledge summary",
            "content_type": "knowledge_summary",
            "metadata": {"title": "Knowledge Title"},
        }
    ],
    acquisition_status="success",
    dropped_item_count=0,
    source_summary={
        "selected_family": "research_knowledge_recall",
        "selected_tool": "research_knowledge_memory_v1",
        "normalized_count": 1,
    },
    execution_summary={"recall_result_count": 1},
    retrieval_trace={"returned_refs": ["knowledge-1"]},
    error_info=None,
)


def test_run_selects_default_tool_and_wraps_result() -> None:
    tool = FakeResearchKnowledgeMemoryTool(SUCCESS_RESULT)
    service = ResearchKnowledgeRecallFamilyService(tool)

    result = asyncio.run(
        service.run(
            ResearchKnowledgeRecallFamilyRequest(
                owner_user_id="user-1",
                query_text=" postgres governance ",
                query_embedding=[0.1, 0.2, 0.3],
                project_scope_id="project-1",
                allowed_visibility_scopes=["project"],
                knowledge_types=["engineering_observation"],
                topic_tags=["postgresql"],
                source_types=["web_page"],
                limit=3,
            )
        )
    )

    assert tool.last_request is not None
    assert tool.last_request.owner_user_id == "user-1"
    assert tool.last_request.query_text == "postgres governance"
    assert tool.last_request.query_embedding == [0.1, 0.2, 0.3]
    assert tool.last_request.project_scope_id == "project-1"
    assert tool.last_request.allowed_visibility_scopes == ["project"]
    assert tool.last_request.knowledge_types == ["engineering_observation"]
    assert tool.last_request.topic_tags == ["postgresql"]
    assert tool.last_request.source_types == ["web_page"]
    assert tool.last_request.limit == 3
    assert result.selected_family == "research_knowledge_recall"
    assert result.candidate_tools == ["research_knowledge_memory_v1"]
    assert result.selected_tool == "research_knowledge_memory_v1"
    assert result.acquisition_status == "success"
    assert result.execution_summary["candidate_tool_count"] == 1
    assert result.retrieval_trace["selected_tool"] == "research_knowledge_memory_v1"


def test_run_honors_valid_preferred_tool() -> None:
    tool = FakeResearchKnowledgeMemoryTool(SUCCESS_RESULT)
    service = ResearchKnowledgeRecallFamilyService(tool)

    result = asyncio.run(
        service.run(
            ResearchKnowledgeRecallFamilyRequest(
                owner_user_id="user-1",
                query_text="postgres",
                preferred_tool="research_knowledge_memory_v1",
            )
        )
    )

    assert result.selected_tool == "research_knowledge_memory_v1"
    assert result.execution_summary["preferred_tool_requested"] == "research_knowledge_memory_v1"


def test_run_returns_failed_for_invalid_preferred_tool() -> None:
    tool = FakeResearchKnowledgeMemoryTool(SUCCESS_RESULT)
    service = ResearchKnowledgeRecallFamilyService(tool)

    result = asyncio.run(
        service.run(
            ResearchKnowledgeRecallFamilyRequest(
                owner_user_id="user-1",
                query_text="postgres",
                preferred_tool="memory_v2",
            )
        )
    )

    assert result.acquisition_status == "failed"
    assert result.selected_tool is None
    assert "Preferred tool 'memory_v2'" in (result.error_info or "")
    assert tool.last_request is None


def test_run_returns_failed_when_no_tool_is_registered() -> None:
    service = ResearchKnowledgeRecallFamilyService(None)

    result = asyncio.run(
        service.run(
            ResearchKnowledgeRecallFamilyRequest(
                owner_user_id="user-1",
                query_text="postgres",
            )
        )
    )

    assert result.acquisition_status == "failed"
    assert result.candidate_tools == []
    assert result.selected_tool is None
    assert (
        result.error_info
        == "No available tools registered for research_knowledge_recall family."
    )


def test_run_preserves_partial_success_no_result_and_failed_statuses() -> None:
    for status in ["partial_success", "no_result", "failed"]:
        tool = FakeResearchKnowledgeMemoryTool(
            ResearchKnowledgeMemoryToolResult(
                normalized_items=[],
                acquisition_status=status,
                dropped_item_count=0,
                source_summary={"selected_tool": "research_knowledge_memory_v1"},
                execution_summary={},
                retrieval_trace={},
                error_info="boom" if status == "failed" else None,
            )
        )
        service = ResearchKnowledgeRecallFamilyService(tool)

        result = asyncio.run(
            service.run(
                ResearchKnowledgeRecallFamilyRequest(
                    owner_user_id="user-1",
                    query_text="postgres",
                )
            )
        )

        assert result.acquisition_status == status
        assert result.selected_family == "research_knowledge_recall"
        assert result.selected_tool == "research_knowledge_memory_v1"
