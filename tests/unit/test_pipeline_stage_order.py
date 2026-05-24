"""Pipeline stage ordering tests."""

import asyncio

from app.domain.models import RequestContext
from app.orchestration.research_action_pipeline import build_default_pipeline


def test_pipeline_stage_order() -> None:
    pipeline = build_default_pipeline()
    output = asyncio.run(
        pipeline.run(
            RequestContext(
                original_query="Compare RAG and agentic retrieval for production systems.",
                session_id="s-1",
                project_id="p-1",
            )
        )
    )
    assert output.stage_history == [
        "request_intake",
        "task_interpretation",
        "context_memory_load",
        "workflow_routing",
        "planning",
        "research",
        "conclusion",
        "memory_writeback",
        "output",
    ]
