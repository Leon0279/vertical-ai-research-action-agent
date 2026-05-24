"""Agent API route definitions."""

from fastapi import APIRouter

from app.api.schemas.action_item_schema import ActionItemSchema
from app.api.schemas.agent_run_request import AgentRunRequest
from app.api.schemas.agent_run_response import AgentRunResponse
from app.api.schemas.citation_schema import CitationSchema
from app.domain.models import RequestContext
from app.orchestration.research_action_pipeline import build_default_pipeline

router = APIRouter(prefix="/v1/agent", tags=["agent"])
_pipeline = build_default_pipeline()


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(payload: AgentRunRequest) -> AgentRunResponse:
    """Single entrypoint for architecture skeleton execution."""

    request_context = RequestContext(
        original_query=payload.query,
        session_id=payload.session_id,
        project_id=payload.project_id,
        constraints=payload.constraints,
        preferences=payload.preferences,
    )

    output = await _pipeline.run(request_context)
    return AgentRunResponse(
        trace_id=output.trace_id,
        task_type=output.task_type.value,
        workflow_pattern=output.workflow_pattern.value,
        summary=output.summary,
        recommendation=output.recommendation,
        action_items=[
            ActionItemSchema(
                title=item.title,
                description=item.description,
                priority=item.priority,
                metadata=item.metadata,
            )
            for item in output.action_items
        ],
        citations=[
            CitationSchema(source=citation.source, note=citation.note)
            for citation in output.citations
        ],
        confidence=output.confidence,
        stage_history=output.stage_history,
        metadata=output.metadata,
    )
