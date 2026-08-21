"""Private memory-domain identity helpers."""

from __future__ import annotations

from app.domain.models import MemoryCandidate


def memory_candidate_dedupe_key(candidate: MemoryCandidate) -> str:
    """构造按 memory 类型和规范化摘要去重的稳定键。"""

    normalized = " ".join(candidate.summary.casefold().split())
    return f"{candidate.memory_type.value}:{normalized}"
