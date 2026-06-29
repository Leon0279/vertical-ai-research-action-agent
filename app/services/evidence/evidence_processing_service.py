"""Evidence Processing service for Tool Execution Layer outputs."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.domain.models import (
    EvidenceProcessingSummary,
    EvidenceProcessingRequest,
    EvidenceProcessingResult,
    NormalizedRetrievalItem,
    ProcessedEvidenceSummary,
    ProcessedEvidenceUnit,
)
from app.domain.models.evidence.processed_evidence_unit import EvidenceType
from app.services.evidence.contracts.evidence_processing_service_protocol import (
    EvidenceProcessingServiceProtocol,
)


class _LLMEvidenceUnitPayload(BaseModel):
    """Strict evidence unit payload expected from the LLM."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    evidence_type: EvidenceType
    support_refs: list[str] = Field(default_factory=list)


class _LLMStructuringPayload(BaseModel):
    """Strict structuring payload expected from the LLM."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["keep", "drop"]
    evidence_units: list[_LLMEvidenceUnitPayload] = Field(default_factory=list)


class EvidenceProcessingService(EvidenceProcessingServiceProtocol):
    """Convert candidate materials into current-round processed evidence units."""

    _POLICY_NAME = "evidence_processing_v1"
    _MIN_CONTENT_LENGTH = 8
    _CONTAINMENT_BLOCKERS = {
        "but",
        "however",
        "although",
        "whereas",
        "while",
        "cost",
        "limitation",
        "risk",
        "tradeoff",
        "trade-off",
    }

    def __init__(self, llm_client: LLMClientProtocol | None = None) -> None:
        self._llm_client = llm_client

    async def process(
        self,
        request: EvidenceProcessingRequest,
    ) -> EvidenceProcessingResult:
        """Process one current-round candidate material set."""

        try:
            if request.acquisition_status in {"no_result", "failed"}:
                return self._empty_result(
                    request=request,
                    processing_status="no_result",
                    reason=f"Upstream acquisition status was {request.acquisition_status}.",
                )

            if not request.normalized_items:
                return self._empty_result(
                    request=request,
                    processing_status="no_result",
                    reason="No normalized candidate materials were provided.",
                )

            deduped_materials, dedup_summary = self._dedup_materials(
                request.normalized_items
            )
            structured_units: list[ProcessedEvidenceUnit] = []
            dropped_material_count = 0
            llm_error_count = 0

            for material in deduped_materials:
                if not self._is_quality_material(material):
                    dropped_material_count += 1
                    continue

                try:
                    units = await self._structure_material(request, material)
                except Exception:
                    llm_error_count += 1
                    dropped_material_count += 1
                    continue

                if not units:
                    dropped_material_count += 1
                    continue
                structured_units.extend(units)

            consolidated_units, consolidation_summary = self._consolidate_evidence(
                structured_units
            )
            final_units = self._assign_evidence_ids(consolidated_units)
            processing_status = self._processing_status(
                output_count=len(final_units),
                llm_error_count=llm_error_count,
                dropped_material_count=dropped_material_count,
                input_count=len(request.normalized_items),
            )

            return EvidenceProcessingResult(
                processed_evidence_units=final_units,
                evidence_summary=self._evidence_summary(final_units),
                evidence_processing_summary={
                    "policy": self._POLICY_NAME,
                    "input_material_count": len(request.normalized_items),
                    "deduped_material_count": len(deduped_materials),
                    "removed_duplicate_count": dedup_summary["removed_duplicate_count"],
                    "exact_duplicate_removed": dedup_summary["exact_duplicate_removed"],
                    "high_overlap_removed": dedup_summary["high_overlap_removed"],
                    "dropped_material_count": dropped_material_count,
                    "structured_evidence_count": len(structured_units),
                    "merged_evidence_count": consolidation_summary[
                        "merged_evidence_count"
                    ],
                    "output_evidence_count": len(final_units),
                    "llm_invalid_output_count": llm_error_count,
                    "upstream_acquisition_status": request.acquisition_status,
                    "upstream_dropped_item_count": request.dropped_item_count,
                },
                processing_status=processing_status,
                error_info=(
                    "Some materials could not be structured."
                    if processing_status == "partial_success"
                    else None
                ),
            )
        except Exception as exc:
            return EvidenceProcessingResult(
                processed_evidence_units=[],
                evidence_summary=self._evidence_summary([]),
                evidence_processing_summary={
                    "policy": self._POLICY_NAME,
                    "input_material_count": len(request.normalized_items),
                    "output_evidence_count": 0,
                },
                processing_status="failed",
                error_info=str(exc),
            )

    def _dedup_materials(
        self,
        materials: list[NormalizedRetrievalItem],
    ) -> tuple[list[NormalizedRetrievalItem], dict[str, int]]:
        kept: list[NormalizedRetrievalItem] = []
        exact_duplicate_removed = 0
        high_overlap_removed = 0

        for material in materials:
            duplicate_index, duplicate_kind = self._find_duplicate(kept, material)
            if duplicate_index is None:
                kept.append(material)
                continue

            if self._should_replace_material(kept[duplicate_index], material):
                kept[duplicate_index] = material
            if duplicate_kind == "exact":
                exact_duplicate_removed += 1
            else:
                high_overlap_removed += 1

        removed_duplicate_count = exact_duplicate_removed + high_overlap_removed
        return kept, {
            "removed_duplicate_count": removed_duplicate_count,
            "exact_duplicate_removed": exact_duplicate_removed,
            "high_overlap_removed": high_overlap_removed,
        }

    def _find_duplicate(
        self,
        kept: list[NormalizedRetrievalItem],
        material: NormalizedRetrievalItem,
    ) -> tuple[int | None, str | None]:
        for index, existing in enumerate(kept):
            if self._is_same_identity_or_exact_duplicate(existing, material):
                return index, "exact"
            if self._is_same_source_containment(existing, material):
                return index, "overlap"
        return None, None

    def _is_same_identity_or_exact_duplicate(
        self,
        left: NormalizedRetrievalItem,
        right: NormalizedRetrievalItem,
    ) -> bool:
        left_item_id = left.item_id.strip()
        right_item_id = right.item_id.strip()
        if left_item_id and left_item_id == right_item_id:
            return True

        return (
            self._source_ref(left) == self._source_ref(right)
            and self._normalized_text(self._content(left))
            == self._normalized_text(self._content(right))
        )

    def _is_same_source_containment(
        self,
        left: NormalizedRetrievalItem,
        right: NormalizedRetrievalItem,
    ) -> bool:
        if self._source_ref(left) != self._source_ref(right):
            return False
        left_content = self._normalized_text(self._content(left))
        right_content = self._normalized_text(self._content(right))
        if not left_content or not right_content or left_content == right_content:
            return False
        return left_content in right_content or right_content in left_content

    def _should_replace_material(
        self,
        existing: NormalizedRetrievalItem,
        candidate: NormalizedRetrievalItem,
    ) -> bool:
        existing_content = self._content(existing)
        candidate_content = self._content(candidate)
        if len(candidate_content) != len(existing_content):
            return len(candidate_content) > len(existing_content)
        return len(self._metadata(candidate)) > len(self._metadata(existing))

    def _is_quality_material(self, material: NormalizedRetrievalItem) -> bool:
        content = self._content(material).strip()
        if not content:
            return False
        if len(self._normalized_text(content)) < self._MIN_CONTENT_LENGTH and not self._metadata(
            material
        ):
            return False
        return True

    async def _structure_material(
        self,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
    ) -> list[ProcessedEvidenceUnit]:
        if self._llm_client is None:
            return [self._fallback_evidence_unit(request, material)]

        prompt = self._build_prompt(request, material)
        llm_output = await self._llm_client.generate_text(prompt)
        payload = self._parse_llm_output(llm_output)
        if payload.decision == "drop":
            return []

        units: list[ProcessedEvidenceUnit] = []
        for payload_unit in payload.evidence_units:
            content = payload_unit.content.strip()
            if not content:
                continue
            support_refs = self._normalize_support_refs(
                payload_unit.support_refs,
                fallback_ref=self._source_ref(material),
            )
            units.append(
                self._evidence_unit(
                    request=request,
                    material=material,
                    content=content,
                    evidence_type=payload_unit.evidence_type,
                    support_refs=support_refs,
                    metadata={"structuring_method": "llm"},
                )
            )
        return units

    def _fallback_evidence_unit(
        self,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
    ) -> ProcessedEvidenceUnit:
        source_ref = self._source_ref(material)
        return self._evidence_unit(
            request=request,
            material=material,
            content=self._content(material).strip(),
            evidence_type="supporting_signal",
            support_refs=[source_ref],
            metadata={"structuring_method": "deterministic_fallback"},
        )

    def _evidence_unit(
        self,
        *,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
        content: str,
        evidence_type: EvidenceType,
        support_refs: list[str],
        metadata: dict[str, Any],
    ) -> ProcessedEvidenceUnit:
        return ProcessedEvidenceUnit(
            evidence_unit_id="pending",
            source_ref=self._source_ref(material),
            source_family=self._source_family(request, material),
            source_type=self._source_type(material),
            content=content,
            evidence_type=evidence_type,
            support_refs=support_refs,
            target_problem=self._optional_trace_string(request, "target_problem"),
            target_scope=self._optional_trace_dict(request, "target_scope"),
            evidence_goal=self._optional_trace_string(request, "evidence_goal"),
            sub_question=self._optional_trace_string(request, "sub_question"),
            comparison_candidate=self._optional_trace_string(
                request, "comparison_candidate"
            ),
            gap=self._optional_trace_string(request, "gap"),
            metadata={
                **metadata,
                "item_id": material.item_id,
                "selected_tool": self._string_value(
                    request.retrieval_trace.get("selected_tool")
                    or request.source_summary.get("selected_tool")
                ),
                "generated_query": self._string_value(
                    request.retrieval_trace.get("generated_query")
                ),
            },
        )

    def _build_prompt(
        self,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
    ) -> str:
        prompt_input = {
            "target_problem": request.retrieval_trace.get("target_problem"),
            "target_scope": request.retrieval_trace.get("target_scope"),
            "evidence_goal": request.retrieval_trace.get("evidence_goal"),
            "sub_question": request.retrieval_trace.get("sub_question"),
            "comparison_candidate": request.retrieval_trace.get(
                "comparison_candidate"
            ),
            "gap": request.retrieval_trace.get("gap"),
            "material": {
                "source_ref": self._source_ref(material),
                "source_family": self._source_family(request, material),
                "source_type": self._source_type(material),
                "content": self._content(material),
                "metadata": self._metadata(material),
            },
        }
        return (
            "你现在负责执行 Evidence Structuring。\n\n"
            "你的任务是：针对一条 dedup 后的 material，判断它是否值得进入当前轮 evidence set；"
            "如果值得，则从中抽取 1 到多个 source-grounded 的 evidence unit，并为每个 evidence unit 标注 evidence_type。\n\n"
            "硬性要求：\n"
            "1. 只能抽取原材料中明确表达或可直接支持的内容。\n"
            "2. 不要做 final reasoning、recommendation 或 action planning。\n"
            "3. 不要重新判断 target_problem、target_scope、evidence_goal、sub_question、comparison_candidate、gap。\n"
            "4. evidence_type 只能是 direct_fact、supporting_signal、comparison_signal、status_signal、background_signal。\n"
            "5. 只输出 JSON，不要输出解释或推理过程。\n\n"
            "输出 JSON 必须且只能包含 decision、evidence_units。\n"
            "decision 必须是 keep 或 drop。\n"
            "每个 evidence unit 必须包含 content、evidence_type、support_refs。\n\n"
            "输入如下：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )

    def _parse_llm_output(self, llm_output: str) -> _LLMStructuringPayload:
        json_text = self._strip_json_code_fence(llm_output)
        try:
            raw_payload = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM response was not valid JSON.") from exc

        try:
            payload = _LLMStructuringPayload.model_validate(raw_payload)
        except ValidationError as exc:
            raise ValueError("LLM response did not match evidence schema.") from exc

        if payload.decision == "drop" and payload.evidence_units:
            raise ValueError("Drop decisions must return an empty evidence_units list.")
        return payload

    def _strip_json_code_fence(self, value: str) -> str:
        stripped = value.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _consolidate_evidence(
        self,
        evidence_units: list[ProcessedEvidenceUnit],
    ) -> tuple[list[ProcessedEvidenceUnit], dict[str, int]]:
        kept: list[ProcessedEvidenceUnit] = []
        exact_match_merged = 0
        containment_merged = 0

        for unit in evidence_units:
            duplicate_index, merge_kind = self._find_evidence_duplicate(kept, unit)
            if duplicate_index is None:
                kept.append(unit)
                continue

            kept[duplicate_index] = self._merge_evidence_units(
                kept[duplicate_index], unit
            )
            if merge_kind == "exact":
                exact_match_merged += 1
            else:
                containment_merged += 1

        return kept, {
            "merged_evidence_count": exact_match_merged + containment_merged,
            "exact_match_merged": exact_match_merged,
            "containment_merged": containment_merged,
        }

    def _find_evidence_duplicate(
        self,
        kept: list[ProcessedEvidenceUnit],
        unit: ProcessedEvidenceUnit,
    ) -> tuple[int | None, str | None]:
        for index, existing in enumerate(kept):
            if existing.evidence_type != unit.evidence_type:
                continue
            existing_content = self._normalized_text(existing.content)
            unit_content = self._normalized_text(unit.content)
            if existing_content == unit_content:
                return index, "exact"
            if self._is_conservative_evidence_containment(existing_content, unit_content):
                return index, "containment"
        return None, None

    def _is_conservative_evidence_containment(self, left: str, right: str) -> bool:
        if not left or not right:
            return False
        shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
        if shorter not in longer:
            return False
        added_tokens = [token for token in longer.split() if token not in set(shorter.split())]
        if len(added_tokens) > 6:
            return False
        return not any(token in self._CONTAINMENT_BLOCKERS for token in added_tokens)

    def _merge_evidence_units(
        self,
        existing: ProcessedEvidenceUnit,
        candidate: ProcessedEvidenceUnit,
    ) -> ProcessedEvidenceUnit:
        canonical = candidate if len(candidate.content) > len(existing.content) else existing
        support_refs = self._merge_ordered_refs(existing.support_refs, candidate.support_refs)
        metadata = {
            **existing.metadata,
            **candidate.metadata,
            "consolidated": True,
        }
        return canonical.model_copy(
            update={
                "support_refs": support_refs,
                "metadata": metadata,
            }
        )

    def _assign_evidence_ids(
        self,
        units: list[ProcessedEvidenceUnit],
    ) -> list[ProcessedEvidenceUnit]:
        return [
            unit.model_copy(update={"evidence_unit_id": f"ev_{index:03d}"})
            for index, unit in enumerate(units, start=1)
        ]

    def _evidence_summary(
        self,
        units: list[ProcessedEvidenceUnit],
    ) -> ProcessedEvidenceSummary:
        type_breakdown: dict[str, int] = {}
        source_families: list[str] = []
        source_types: list[str] = []

        for unit in units:
            type_breakdown[unit.evidence_type] = type_breakdown.get(unit.evidence_type, 0) + 1
            if unit.source_family and unit.source_family not in source_families:
                source_families.append(unit.source_family)
            if unit.source_type and unit.source_type not in source_types:
                source_types.append(unit.source_type)

        return ProcessedEvidenceSummary(
            new_evidence_count=len(units),
            evidence_type_breakdown=type_breakdown,
            source_coverage_summary={
                "source_families": source_families,
                "source_types": source_types,
            },
        )

    def _processing_status(
        self,
        *,
        output_count: int,
        llm_error_count: int,
        dropped_material_count: int,
        input_count: int,
    ) -> str:
        if output_count == 0:
            return "no_result"
        if llm_error_count > 0 or dropped_material_count > max(0, input_count - output_count):
            return "partial_success"
        return "success"

    def _empty_result(
        self,
        *,
        request: EvidenceProcessingRequest,
        processing_status: str,
        reason: str,
    ) -> EvidenceProcessingResult:
        return EvidenceProcessingResult(
            processed_evidence_units=[],
            evidence_summary=self._evidence_summary([]),
            evidence_processing_summary={
                "policy": self._POLICY_NAME,
                "input_material_count": len(request.normalized_items),
                "deduped_material_count": 0,
                "removed_duplicate_count": 0,
                "dropped_material_count": 0,
                "structured_evidence_count": 0,
                "merged_evidence_count": 0,
                "output_evidence_count": 0,
                "upstream_acquisition_status": request.acquisition_status,
                "short_circuit_reason": reason,
            },
            processing_status=processing_status,
            error_info=None,
        )

    def _source_ref(self, material: NormalizedRetrievalItem) -> str:
        return material.source_ref.strip() or material.item_id.strip() or "unknown_source"

    def _source_family(
        self,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
    ) -> str:
        return (
            material.source_family.strip()
            or self._string_value(request.retrieval_trace.get("selected_family"))
            or self._string_value(request.source_summary.get("selected_family"))
            or "unknown_family"
        )

    def _source_type(self, material: NormalizedRetrievalItem) -> str:
        return material.source_type.strip() or "unknown_source_type"

    def _content(self, material: NormalizedRetrievalItem) -> str:
        return material.content

    def _metadata(self, material: NormalizedRetrievalItem) -> dict[str, Any]:
        return material.metadata

    def _optional_trace_string(
        self,
        request: EvidenceProcessingRequest,
        key: str,
    ) -> str | None:
        value = request.retrieval_trace.get(key)
        return self._string_value(value) or None

    def _optional_trace_dict(
        self,
        request: EvidenceProcessingRequest,
        key: str,
    ) -> dict[str, Any] | None:
        value = request.retrieval_trace.get(key)
        return value if isinstance(value, dict) else None

    def _normalize_support_refs(
        self,
        refs: list[str],
        *,
        fallback_ref: str,
    ) -> list[str]:
        normalized = [ref.strip() for ref in refs if ref.strip()]
        if not normalized:
            normalized = [fallback_ref]
        return self._merge_ordered_refs([], normalized)

    def _merge_ordered_refs(self, left: list[str], right: list[str]) -> list[str]:
        merged: list[str] = []
        for ref in [*left, *right]:
            if ref and ref not in merged:
                merged.append(ref)
        return merged

    def _string_value(self, value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    def _normalized_text(self, value: str) -> str:
        lower = value.lower().strip()
        without_punctuation = re.sub(r"[^\w\s]", " ", lower)
        return re.sub(r"\s+", " ", without_punctuation).strip()
