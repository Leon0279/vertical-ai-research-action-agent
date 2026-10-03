"""Research Executor 内部的检索历史压缩与路径规避协作者。"""

from __future__ import annotations

import hashlib
import logging

from app.common.utils.text import normalize_whitespace_or_none
from app.domain.enums import AcquisitionStatus, RetrievalResultUtility
from app.domain.models import RecentRetrievalAttempt, ToolExecutionLayerResult
from app.services.executor.enums import ResearchEvidenceGain, ResearchTopGapProgress
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)

logger = logging.getLogger(__name__)


class ResearchRetrievalHistoryTracker:
    """将本轮 TEL 结果压缩为下一轮可消费的最小检索历史。

    该协作者只维护一次 Research Stage 内的检索经验，不保存 raw trace、不做检索决策，
    也不写入 RunningState、长期记忆或任何公开 result。ResearchStateAssessor 将其作为
    LLM 的参考信息，TEL 可消费与当前 target 相关的历史投影，但历史不会形成 family blacklist。
    """

    _MAX_RECENT_ATTEMPTS = 30

    def record_completed_iteration(self, run_state: ResearchExecutorRunState) -> None:
        """在 Step 7 后压缩当前 iteration 的实际 retrieval attempts。"""

        iteration = run_state.require_current_iteration()
        tool_execution_result = iteration.tool_execution_result
        next_evidence_need = run_state.next_evidence_need
        if tool_execution_result is None:
            self._log_history_update(
                run_state,
                coverage_target_key=(
                    next_evidence_need.coverage_target_key
                    if next_evidence_need is not None
                    else None
                ),
                update_status="skipped",
                skip_reason="no_tool_execution_result",
            )
            return
        if next_evidence_need is None:
            self._log_history_update(
                run_state,
                coverage_target_key=None,
                update_status="skipped",
                skip_reason="no_next_evidence_need",
            )
            return

        attempts = tool_execution_result.retrieval_trace.attempts
        if not attempts:
            self._log_history_update(
                run_state,
                coverage_target_key=next_evidence_need.coverage_target_key,
                update_status="skipped",
                skip_reason="no_retrieval_attempt",
            )
            return

        compressed_attempts: list[RecentRetrievalAttempt] = []
        for attempt in attempts:
            selected_family = (
                attempt.selected_family
                or tool_execution_result.retrieval_trace.selected_family
            )
            if selected_family is None:
                continue
            target_problem = self._target_problem(tool_execution_result, iteration)
            if target_problem is None:
                continue
            generated_query = normalize_whitespace_or_none(attempt.generated_query)
            acquisition_status = (
                attempt.acquisition_status
                or tool_execution_result.acquisition_status
            )
            compressed_attempts.append(
                RecentRetrievalAttempt(
                    coverage_target_key=next_evidence_need.coverage_target_key,
                    selected_family=selected_family,
                    selected_tool=(
                        attempt.selected_tool
                        or tool_execution_result.retrieval_trace.selected_tool
                    ),
                    target_problem=target_problem,
                    generated_query=generated_query,
                    query_fingerprint=(
                        self.query_fingerprint(generated_query) or "no_query"
                    ),
                    result_status=acquisition_status,
                    result_utility=self._attempt_utility(
                        run_state,
                        acquisition_status,
                    ),
                    fallback_applied=attempt.fallback_applied,
                )
            )

        if not compressed_attempts:
            self._log_history_update(
                run_state,
                coverage_target_key=next_evidence_need.coverage_target_key,
                update_status="skipped",
                skip_reason="no_valid_attempt",
            )
            return

        combined_attempts = [
            *run_state.recent_retrieval_attempts,
            *compressed_attempts,
        ]
        truncated_count = max(
            0,
            len(combined_attempts) - self._MAX_RECENT_ATTEMPTS,
        )
        run_state.recent_retrieval_attempts = combined_attempts[
            -self._MAX_RECENT_ATTEMPTS :
        ]
        self._log_history_update(
            run_state,
            coverage_target_key=next_evidence_need.coverage_target_key,
            update_status="updated",
            new_attempts=compressed_attempts,
            truncated_count=truncated_count,
        )

    def _log_history_update(
        self,
        run_state: ResearchExecutorRunState,
        *,
        coverage_target_key: str | None,
        update_status: str,
        skip_reason: str | None = None,
        new_attempts: list[RecentRetrievalAttempt] | None = None,
        truncated_count: int = 0,
    ) -> None:
        """记录压缩后的本轮 history 变化，不记录 raw query 或完整历史。"""

        iteration = run_state.require_current_iteration()
        attempts = list(new_attempts or [])
        logger.info(
            "Research retrieval history processed.",
            extra={
                "event": "research_retrieval_history_updated",
                "iteration_index": iteration.iteration_index,
                "remaining_iteration_budget": iteration.remaining_iteration_budget,
                "coverage_target_key": coverage_target_key,
                "history_update_status": update_status,
                "history_skip_reason": skip_reason,
                "new_retrieval_attempt_count": len(attempts),
                "retrieval_history_count": len(
                    run_state.recent_retrieval_attempts
                ),
                "retrieval_history_truncated_count": truncated_count,
                "retrieval_attempts": [
                    {
                        "selected_family": attempt.selected_family,
                        "selected_tool": attempt.selected_tool,
                        "query_fingerprint": attempt.query_fingerprint,
                        "result_status": attempt.result_status,
                        "result_utility": attempt.result_utility,
                        "fallback_applied": attempt.fallback_applied,
                    }
                    for attempt in attempts
                ],
            },
        )

    def attempts_for_target(
        self,
        recent_retrieval_attempts: list[RecentRetrievalAttempt],
        coverage_target_key: str,
    ) -> list[RecentRetrievalAttempt]:
        """返回与当前 coverage target 精确对应的近期尝试。"""

        return [
            attempt
            for attempt in recent_retrieval_attempts
            if attempt.coverage_target_key == coverage_target_key
        ]

    def assessment_prompt_value(
        self,
        recent_retrieval_attempts: list[RecentRetrievalAttempt],
    ) -> list[dict[str, object]]:
        """将 typed history 转为 assessment LLM 可理解且不含 raw trace 的摘要。"""

        return [
            {
                "coverage_target_key": attempt.coverage_target_key,
                "selected_family": attempt.selected_family.value,
                "selected_tool": attempt.selected_tool,
                "target_problem": attempt.target_problem,
                "generated_query": attempt.generated_query,
                "query_fingerprint": attempt.query_fingerprint,
                "result_status": attempt.result_status.value,
                "result_utility": attempt.result_utility.value,
                "fallback_applied": attempt.fallback_applied,
            }
            for attempt in recent_retrieval_attempts
        ]

    def _target_problem(
        self,
        tool_execution_result: ToolExecutionLayerResult,
        iteration: ResearchExecutorIterationState,
    ) -> str | None:
        """优先从 TEL trace 读取实际 target，再回退当前 TEL request。"""

        return normalize_whitespace_or_none(
            tool_execution_result.retrieval_trace.target_problem
            or (
                iteration.tool_execution_request.target_problem
                if iteration.tool_execution_request is not None
                else None
            )
        )

    def _attempt_utility(
        self,
        run_state: ResearchExecutorRunState,
        acquisition_status: AcquisitionStatus,
    ) -> RetrievalResultUtility:
        """结合 Evidence Processing 与 Step 7 outcome 确定单条 attempt 的实际效用。"""

        iteration = run_state.require_current_iteration()
        if acquisition_status in {
            AcquisitionStatus.FAILED,
            AcquisitionStatus.NO_RESULT,
        }:
            return RetrievalResultUtility.NOT_USEFUL
        if (
            iteration.evidence_processing_result is None
            or iteration.evidence_processing_result.processing_status
            in {"failed", "no_result"}
            or not iteration.processed_evidence_units
        ):
            return RetrievalResultUtility.NOT_USEFUL

        evaluation_state = iteration.evaluation_state
        if evaluation_state is None or evaluation_state.evidence_gain is None:
            return RetrievalResultUtility.WEAKLY_USEFUL
        if evaluation_state.evidence_gain == ResearchEvidenceGain.LIMITED_GAIN:
            return RetrievalResultUtility.WEAKLY_USEFUL
        if evaluation_state.evidence_gain != ResearchEvidenceGain.MEANINGFUL_GAIN:
            return RetrievalResultUtility.NOT_USEFUL
        if evaluation_state.top_gap_progress == ResearchTopGapProgress.RESOLVED:
            return RetrievalResultUtility.HIGHLY_USEFUL
        if (
            evaluation_state.top_gap_progress
            == ResearchTopGapProgress.PARTIALLY_ADVANCED
        ):
            return RetrievalResultUtility.STRONGLY_USEFUL
        return RetrievalResultUtility.USEFUL

    def query_fingerprint(self, generated_query: str | None) -> str | None:
        """生成足够稳定且不引入额外持久化依赖的 query 指纹。"""

        if generated_query is None:
            return None
        normalized_query = generated_query.casefold()
        return hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()[:16]
