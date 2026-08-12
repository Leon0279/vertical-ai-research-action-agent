"""Tests for memory candidate extraction."""

import asyncio

from app.domain.models import ExecutionContext, RunningState, RuntimeContext, SourceReference
from app.services.memory.memory_distiller_service import MemoryDistillerService


def _context(
    *,
    confidence: str | None = "high",
    caveats: list[str] | None = None,
    open_questions: list[str] | None = None,
    final_recommendation: str | None = "优先建设离线评测集。",
) -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(
            original_query="如何提升检索质量？",
            project_scope_id="project-1",
            final_recommendation=final_recommendation,
            confidence=confidence,
            caveats=caveats or [],
            open_questions=open_questions or [],
            retrieved_evidence_refs=[
                SourceReference(
                    source_type="document",
                    source_id="docs-1",
                    source_id_type="docs_entry_id",
                    source_url="https://docs.example/1",
                )
            ],
        ),
        runtime_context=RuntimeContext(
            request_id="run-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )


def test_distiller_maps_decision_candidate_metadata() -> None:
    candidates = asyncio.run(MemoryDistillerService().distill(_context()))

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.memory_type.value == "DECISION"
    assert candidate.semantic_type == "stable_decision"
    assert candidate.candidate_source == "run_output"
    assert candidate.project_scope_id == "project-1"
    assert candidate.derived_from_run_id == "run-1"
    assert candidate.derived_from_session_id == "session-1"
    assert candidate.source_references[0].source_id == "docs-1"
    assert candidate.confidence == 0.8
    assert candidate.stability == "stable"
    assert candidate.payload == {"task_type": None}


def test_distiller_marks_uncertain_candidate_tentative() -> None:
    candidates = asyncio.run(
        MemoryDistillerService().distill(
            _context(confidence="high", caveats=["证据覆盖仍有限"])
        )
    )

    assert candidates[0].stability == "tentative"


def test_distiller_does_not_create_candidate_without_recommendation() -> None:
    candidates = asyncio.run(
        MemoryDistillerService().distill(_context(final_recommendation=None))
    )

    assert candidates == []

