"""Tests for memory candidate persistence shaping."""

import asyncio

from app.domain.enums.memory_type import MemoryType
from app.domain.models import MemoryCandidate, SourceReference
from app.services.memory.memory_persistence_service import MemoryPersistenceService


class _FakeLongTermStore:
    def __init__(self) -> None:
        self.records = []
        self.call_count = 0

    async def upsert(self, records) -> None:
        self.call_count += 1
        self.records.extend(records)


def _candidate() -> MemoryCandidate:
    return MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="优先建设离线评测集。",
        payload={
            "task_type": "RECOMMENDATION",
            "summary": "payload 不应覆盖 canonical summary",
            "stability": "payload 不应覆盖 canonical stability",
            "source_references": "payload 不应覆盖 canonical refs",
        },
        confidence=0.8,
        stability="stable",
        project_scope_id="project-1",
        candidate_source="run_output",
        semantic_type="stable_decision",
        source_references=[
            SourceReference(
                source_type="document",
                source_id="docs-1",
                source_id_type="docs_entry_id",
                source_url="https://docs.example/1",
            )
        ],
        derived_from_run_id="run-1",
        derived_from_session_id="session-1",
    )


def test_persistence_preserves_canonical_candidate_metadata() -> None:
    store = _FakeLongTermStore()
    asyncio.run(MemoryPersistenceService(store).persist([_candidate()]))

    assert store.call_count == 1
    assert len(store.records) == 1
    payload = store.records[0].payload
    assert payload["summary"] == "优先建设离线评测集。"
    assert payload["stability"] == "stable"
    assert payload["project_scope_id"] == "project-1"
    assert payload["candidate_source"] == "run_output"
    assert payload["semantic_type"] == "stable_decision"
    assert payload["confidence"] == 0.8
    assert payload["derived_from_run_id"] == "run-1"
    assert payload["derived_from_session_id"] == "session-1"
    assert payload["source_references"][0]["source_id"] == "docs-1"
    assert payload["task_type"] == "RECOMMENDATION"


def test_persistence_skips_store_for_empty_candidates() -> None:
    store = _FakeLongTermStore()
    asyncio.run(MemoryPersistenceService(store).persist([]))

    assert store.call_count == 0
    assert store.records == []


def test_persistence_shapes_multiple_candidates() -> None:
    store = _FakeLongTermStore()
    candidates = [_candidate(), _candidate().model_copy(update={"summary": "第二条候选。"})]

    asyncio.run(MemoryPersistenceService(store).persist(candidates))

    assert len(store.records) == 2
    assert [record.payload["summary"] for record in store.records] == [
        "优先建设离线评测集。",
        "第二条候选。",
    ]

