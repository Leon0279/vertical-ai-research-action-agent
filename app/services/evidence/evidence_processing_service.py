"""Evidence Processing service for Tool Execution Layer outputs."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.domain.enums import AcquisitionStatus, FamilyName
from app.domain.models import (
    EvidenceProcessingSummary,
    EvidenceProcessingRequest,
    EvidenceProcessingResult,
    NormalizedRetrievalItem,
    ProcessedEvidenceSummary,
    ProcessedEvidenceUnit,
    SourceReference,
)
from app.domain.models.evidence.processed_evidence_unit import EvidenceType
from app.services.evidence.contracts.evidence_processing_service_protocol import (
    EvidenceProcessingServiceProtocol,
)


class _LLMEvidenceUnitPayload(BaseModel):
    """表示大语言模型证据单元的内部结构化载荷。

Strict evidence unit payload expected from the LLM."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(
        min_length=1,
        description="必填字段。LLM 从单条候选材料中保留的结构化证据正文，不应包含来源 attribution 或推理过程。",
    )
    evidence_type: EvidenceType = Field(
        description="必填字段。该证据单元的归一化类型，用于后续 evidence consolidation 和 coverage 统计。",
    )


class _LLMStructuringPayload(BaseModel):
    """表示大语言模型结构化的内部结构化载荷。

Strict structuring payload expected from the LLM."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["keep", "drop"] = Field(
        description="必填字段。LLM 对当前候选材料的结构化处理决定：keep 表示保留证据，drop 表示丢弃。",
    )
    evidence_units: list[_LLMEvidenceUnitPayload] = Field(
        default_factory=list,
        description="可选字段，默认空列表。当 decision 为 keep 时从材料提取出的一个或多个 evidence unit；drop 时应为空。",
    )


class EvidenceProcessingService(EvidenceProcessingServiceProtocol):
    """负责处理证据处理相关业务逻辑的服务。

Convert candidate materials into current-round processed evidence units."""

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
            short_circuit_result = self._short_circuit_result(request)
            if short_circuit_result is not None:
                return short_circuit_result

            deduped_materials, dedup_summary = self._dedup_materials(
                request.normalized_items
            )
            (
                structured_units,
                dropped_material_count,
                llm_error_count,
            ) = await self._structure_materials(request, deduped_materials)
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

            return self._create_result(
                request=request,
                final_units=final_units,
                deduped_material_count=len(deduped_materials),
                dedup_summary=dedup_summary,
                dropped_material_count=dropped_material_count,
                structured_evidence_count=len(structured_units),
                consolidation_summary=consolidation_summary,
                llm_error_count=llm_error_count,
                processing_status=processing_status,
            )
        except Exception as exc:
            return self._create_failed_result(request=request, error_info=str(exc))

    def _short_circuit_result(
        self,
        request: EvidenceProcessingRequest,
    ) -> EvidenceProcessingResult | None:
        if request.acquisition_status in {
            AcquisitionStatus.NO_RESULT,
            AcquisitionStatus.FAILED,
        }:
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

        return None

    async def _structure_materials(
        self,
        request: EvidenceProcessingRequest,
        materials: list[NormalizedRetrievalItem],
    ) -> tuple[list[ProcessedEvidenceUnit], int, int]:
        structured_units: list[ProcessedEvidenceUnit] = []
        dropped_material_count = 0
        llm_error_count = 0

        for material in materials:
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

        return structured_units, dropped_material_count, llm_error_count

    def _create_result(
        self,
        *,
        request: EvidenceProcessingRequest,
        final_units: list[ProcessedEvidenceUnit],
        deduped_material_count: int,
        dedup_summary: dict[str, int],
        dropped_material_count: int,
        structured_evidence_count: int,
        consolidation_summary: dict[str, int],
        llm_error_count: int,
        processing_status: str,
    ) -> EvidenceProcessingResult:
        return EvidenceProcessingResult(
            processed_evidence_units=final_units,
            evidence_summary=self._evidence_summary(final_units),
            evidence_processing_summary=EvidenceProcessingSummary(
                policy=self._POLICY_NAME,
                input_material_count=len(request.normalized_items),
                deduped_material_count=deduped_material_count,
                removed_duplicate_count=dedup_summary["removed_duplicate_count"],
                exact_duplicate_removed=dedup_summary["exact_duplicate_removed"],
                high_overlap_removed=dedup_summary["high_overlap_removed"],
                dropped_material_count=dropped_material_count,
                structured_evidence_count=structured_evidence_count,
                merged_evidence_count=consolidation_summary["merged_evidence_count"],
                output_evidence_count=len(final_units),
                llm_invalid_output_count=llm_error_count,
                upstream_acquisition_status=request.acquisition_status,
                upstream_dropped_item_count=request.dropped_item_count,
            ),
            processing_status=processing_status,
            error_info=(
                "Some materials could not be structured."
                if processing_status == "partial_success"
                else None
            ),
        )

    def _create_failed_result(
        self,
        *,
        request: EvidenceProcessingRequest,
        error_info: str,
    ) -> EvidenceProcessingResult:
        return EvidenceProcessingResult(
            processed_evidence_units=[],
            evidence_summary=self._evidence_summary([]),
            evidence_processing_summary=EvidenceProcessingSummary(
                policy=self._POLICY_NAME,
                input_material_count=len(request.normalized_items),
                output_evidence_count=0,
            ),
            processing_status="failed",
            error_info=error_info,
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
            units.append(
                self._evidence_unit(
                    request=request,
                    material=material,
                    content=content,
                    evidence_type=payload_unit.evidence_type,
                    metadata={"structuring_method": "llm"},
                )
            )
        return units

    def _fallback_evidence_unit(
        self,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
    ) -> ProcessedEvidenceUnit:
        return self._evidence_unit(
            request=request,
            material=material,
            content=self._content(material).strip(),
            evidence_type="supporting_signal",
            metadata={"structuring_method": "deterministic_fallback"},
        )

    def _evidence_unit(
        self,
        *,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
        content: str,
        evidence_type: EvidenceType,
        metadata: dict[str, Any],
    ) -> ProcessedEvidenceUnit:
        return ProcessedEvidenceUnit(
            evidence_unit_id="pending",
            source_references=material.source_references,
            source_family=self._source_family(request, material),
            content=content,
            evidence_type=evidence_type,
            target_problem=request.retrieval_trace.target_problem,
            target_scope=self._optional_context_dict(request, "target_scope"),
            evidence_goal=self._optional_context_string(request, "evidence_goal"),
            sub_question=self._optional_context_string(request, "sub_question"),
            comparison_candidate=self._optional_context_string(
                request, "comparison_candidate"
            ),
            gap=self._optional_context_string(request, "gap"),
            metadata={
                **metadata,
                "item_id": material.item_id,
                "selected_tool": self._string_value(
                    request.retrieval_trace.selected_tool
                    or request.source_summary.selected_tool
                ),
                "generated_query": self._string_value(request.retrieval_trace.generated_query),
            },
        )

    def _build_prompt(
        self,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
    ) -> str:
        material_input: dict[str, Any] = {
            "content": self._content(material),
            "source_types": self._source_types(material),
        }
        material_context = self._prompt_material_context(material)
        if material_context:
            material_input["context"] = material_context

        prompt_input = {
            "task_context": {
                "target_problem": request.retrieval_trace.target_problem,
                "target_scope": request.retrieval_trace.context.get("target_scope"),
                "evidence_goal": request.retrieval_trace.context.get("evidence_goal"),
                "sub_question": request.retrieval_trace.context.get("sub_question"),
                "comparison_candidate": request.retrieval_trace.context.get(
                    "comparison_candidate"
                ),
                "gap": request.retrieval_trace.context.get("gap"),
            },
            "material": material_input,
        }
        return (
            "你正在执行一次无状态的证据材料整理任务。你只能依据本提示中的说明和最后给出的输入 JSON 工作，"
            "不能假设自己知道历史对话、项目资料或任何未提供的信息。\n\n"
            "任务目标：判断一段材料是否包含能够直接支持当前研究问题的内容。若包含，提炼一条或多条简短证据；"
            "若不包含，选择丢弃。你不需要回答用户问题，也不需要给出最终结论、推荐或行动计划。\n\n"
            "输入 JSON 字段说明：\n"
            "- task_context：当前研究问题及其边界。target_problem 是判断材料相关性的主对象；"
            "target_scope、evidence_goal、sub_question、comparison_candidate 和 gap 是可选的补充边界。\n"
            "- material.content：需要判断和提炼的原始材料正文。\n"
            "- material.source_types：材料的来源类别，仅用于帮助理解材料语境。\n"
            "- material.context：若存在，包含标题、章节、发布时间或资料子类型等辅助信息。\n\n"
            "整理规则：\n"
            "1. 只能保留 material.content 中明确表达或可直接支持的内容；不要补充外部知识或推测。\n"
            "2. 不要改变 task_context 中的研究问题、范围、子问题、比较对象或信息缺口。\n"
            "3. decision 为 keep 时，可以提炼一条或多条证据；每条都应简短、具体且与研究问题相关。\n"
            "4. evidence_type 只能是以下值之一：direct_fact（直接事实）、supporting_signal（支持性信号）、"
            "comparison_signal（比较信号）、status_signal（状态信号）、background_signal（背景信号）。\n"
            "5. 系统会另行关联材料来源，因此不要输出来源链接、来源标识或任何其他关联信息。\n\n"
            "只输出一个 JSON object，不要输出 Markdown、解释文字或推理过程。JSON 必须且只能包含：\n"
            "{\n"
            '  "decision": "keep 或 drop",\n'
            '  "evidence_units": [\n'
            "    {\n"
            '      "content": "从材料中提炼的简短证据",\n'
            '      "evidence_type": "direct_fact | supporting_signal | comparison_signal | status_signal | background_signal"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "当 decision 为 drop 时，evidence_units 必须是空数组。\n\n"
            "输入 JSON：\n"
            f"{json.dumps(prompt_input, ensure_ascii=False, indent=2)}"
        )

    def _prompt_material_context(
        self,
        material: NormalizedRetrievalItem,
    ) -> dict[str, Any]:
        metadata = self._metadata(material)
        context: dict[str, Any] = {}
        for key in ("title", "section", "published_at", "sub_source_type"):
            if key not in metadata:
                continue
            value = metadata[key]
            if value in (None, "", [], {}):
                continue
            context[key] = self._json_safe_prompt_value(value)
        return context

    def _json_safe_prompt_value(self, value: Any) -> Any:
        try:
            json.dumps(value, ensure_ascii=False)
        except TypeError:
            return str(value)
        return value

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
        source_references = self._merge_source_references(
            existing.source_references,
            candidate.source_references,
        )
        metadata = {
            **existing.metadata,
            **candidate.metadata,
            "consolidated": True,
        }
        return canonical.model_copy(
            update={
                "source_references": source_references,
                "metadata": metadata,
            }
        )

    def _merge_source_references(
        self,
        left: list[SourceReference],
        right: list[SourceReference],
    ) -> list[SourceReference]:
        merged: list[SourceReference] = []
        seen: set[str] = set()

        for source_reference in [*left, *right]:
            key = self._source_reference_key(source_reference)
            if key in seen:
                continue
            seen.add(key)
            merged.append(source_reference)

        return merged

    def _source_reference_key(self, source_reference: SourceReference) -> str:
        source_url = (source_reference.source_url or "").strip()
        if source_url:
            return f"url:{source_url}"

        source_id = (source_reference.source_id or "").strip()
        if source_id:
            source_id_type = (source_reference.source_id_type or "").strip()
            return f"id:{source_id_type}:{source_id}"

        return json.dumps(
            source_reference.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
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
            if unit.source_family and unit.source_family.value not in source_families:
                source_families.append(unit.source_family.value)
            for source_type in self._evidence_unit_source_types(unit):
                if source_type not in source_types:
                    source_types.append(source_type)

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
            evidence_processing_summary=EvidenceProcessingSummary(
                policy=self._POLICY_NAME,
                input_material_count=len(request.normalized_items),
                deduped_material_count=0,
                removed_duplicate_count=0,
                dropped_material_count=0,
                structured_evidence_count=0,
                merged_evidence_count=0,
                output_evidence_count=0,
                upstream_acquisition_status=request.acquisition_status,
                short_circuit_reason=reason,
            ),
            processing_status=processing_status,
            error_info=None,
        )

    def _source_ref(self, material: NormalizedRetrievalItem) -> str:
        source_reference = self._primary_source_reference(material)
        return (
            (source_reference.source_url or "").strip()
            or (source_reference.source_id or "").strip()
            or material.item_id.strip()
            or "unknown_source"
        )

    def _source_refs(self, material: NormalizedRetrievalItem) -> list[str]:
        refs: list[str] = []
        for source_reference in material.source_references:
            ref = (
                (source_reference.source_url or "").strip()
                or (source_reference.source_id or "").strip()
            )
            if ref and ref not in refs:
                refs.append(ref)

        if not refs:
            refs.append(material.item_id.strip() or "unknown_source")
        return refs

    def _primary_source_reference(
        self,
        material: NormalizedRetrievalItem,
    ) -> SourceReference:
        return material.source_references[0]

    def _source_family(
        self,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
    ) -> FamilyName | None:
        if material.source_family is not None:
            return material.source_family

        trace_family = self._family_name_value(request.retrieval_trace.get("selected_family"))
        if trace_family is not None:
            return trace_family

        return self._family_name_value(request.source_summary.get("selected_family"))

    def _source_types(self, material: NormalizedRetrievalItem) -> list[str]:
        source_types: list[str] = []
        for source_reference in material.source_references:
            source_type = source_reference.source_type.strip()
            if source_type and source_type not in source_types:
                source_types.append(source_type)
        return source_types

    def _evidence_unit_source_types(
        self,
        unit: ProcessedEvidenceUnit,
    ) -> list[str]:
        source_types: list[str] = []
        for source_reference in unit.source_references:
            source_type = source_reference.source_type.strip()
            if source_type and source_type not in source_types:
                source_types.append(source_type)
        return source_types

    def _family_name_value(self, value: Any) -> FamilyName | None:
        if isinstance(value, FamilyName):
            return value
        if isinstance(value, str):
            try:
                return FamilyName(value)
            except ValueError:
                return None
        return None

    def _content(self, material: NormalizedRetrievalItem) -> str:
        return material.content

    def _metadata(self, material: NormalizedRetrievalItem) -> dict[str, Any]:
        return material.metadata

    def _optional_context_string(
        self,
        request: EvidenceProcessingRequest,
        key: str,
    ) -> str | None:
        value = request.retrieval_trace.context.get(key)
        return self._string_value(value) or None

    def _optional_context_dict(
        self,
        request: EvidenceProcessingRequest,
        key: str,
    ) -> dict[str, Any] | None:
        value = request.retrieval_trace.context.get(key)
        return value if isinstance(value, dict) else None

    def _string_value(self, value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    def _normalized_text(self, value: str) -> str:
        lower = value.lower().strip()
        without_punctuation = re.sub(r"[^\w\s]", " ", lower)
        return re.sub(r"\s+", " ", without_punctuation).strip()
