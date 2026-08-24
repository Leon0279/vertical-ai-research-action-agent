"""Research Executor 内部的检索历史压缩与路径规避协作者。"""

from __future__ import annotations

import hashlib

from app.common.utils.text import normalize_whitespace_or_none
from app.domain.enums import AcquisitionStatus, FamilyName, RetrievalResultUtility
from app.domain.models import RecentRetrievalAttempt, ToolExecutionLayerResult
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)


class ResearchRetrievalHistoryTracker:
    """将本轮 TEL 结果压缩为下一轮可消费的最小检索历史。

    该协作者只维护一次 Research Stage 内的路径经验，不保存 raw trace、不做检索决策，
    也不写入 RunningState、长期记忆或任何公开 result。ResearchActionDecider 读取它的
    typed 结果决定高层路径，TEL 只消费其投影后的 query 负例。
    """

    _MAX_RECENT_ATTEMPTS = 8

    def record_completed_iteration(self, run_state: ResearchExecutorRunState) -> None:
        """在 Step 7 后压缩当前 iteration 的实际 retrieval attempts。"""

        iteration = run_state.require_current_iteration()
        tool_execution_result = iteration.tool_execution_result
        next_evidence_need = run_state.next_evidence_need
        if tool_execution_result is None or next_evidence_need is None:
            return

        attempts = tool_execution_result.retrieval_trace.attempts
        if not attempts:
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
                        self._query_fingerprint(generated_query) or "no_query"
                    ),
                    result_status=acquisition_status,
                    result_utility=self._attempt_utility(
                        run_state,
                        acquisition_status,
                    ),
                    fallback_applied=attempt.fallback_applied,
                )
            )

        run_state.recent_retrieval_attempts = (
            [*run_state.recent_retrieval_attempts, *compressed_attempts]
        )[-self._MAX_RECENT_ATTEMPTS :]

    def attempts_for_target(
        self,
        run_state: ResearchExecutorRunState,
        coverage_target_key: str,
    ) -> list[RecentRetrievalAttempt]:
        """返回与当前 coverage target 精确对应的近期尝试。"""

        return [
            attempt
            for attempt in run_state.recent_retrieval_attempts
            if attempt.coverage_target_key == coverage_target_key
        ]

    def low_value_families_for_target(
        self,
        run_state: ResearchExecutorRunState,
        coverage_target_key: str,
    ) -> set[FamilyName]:
        """依据每个 family 的最近一次结果返回当前 target 应规避的路径。"""

        latest_attempt_by_family: dict[FamilyName, RecentRetrievalAttempt] = {}
        for attempt in self.attempts_for_target(run_state, coverage_target_key):
            latest_attempt_by_family[attempt.selected_family] = attempt
        return {
            family
            for family, attempt in latest_attempt_by_family.items()
            if self.is_definitively_low_value(attempt)
        }

    def is_definitively_low_value(
        self,
        attempt: RecentRetrievalAttempt,
    ) -> bool:
        """判断某条历史是否足以阻止当前 target 立刻重复同一 family。"""

        return (
            attempt.result_status
            in {AcquisitionStatus.FAILED, AcquisitionStatus.NO_RESULT}
            or attempt.result_utility == RetrievalResultUtility.NOT_USEFUL
        )

    def assessment_prompt_value(
        self,
        run_state: ResearchExecutorRunState,
    ) -> list[dict[str, object]]:
        """将 typed history 转为 assessment LLM 可理解且不含 raw trace 的摘要。"""

        return [
            {
                "coverage_target_key": attempt.coverage_target_key,
                "selected_family": attempt.selected_family.value,
                "selected_tool": attempt.selected_tool,
                "target_problem": attempt.target_problem,
                "query_fingerprint": attempt.query_fingerprint,
                "result_status": attempt.result_status.value,
                "result_utility": attempt.result_utility.value,
                "fallback_applied": attempt.fallback_applied,
            }
            for attempt in run_state.recent_retrieval_attempts
        ]

    def _target_problem(
        self,
        tool_execution_result: ToolExecutionLayerResult,
        iteration: ResearchExecutorIterationState,
    ) -> str | None:
        """优先从 TEL trace 读取实际 target，再回退当前 action request。"""

        return normalize_whitespace_or_none(
            tool_execution_result.retrieval_trace.target_problem
            or (
                iteration.action_request.target_problem
                if iteration.action_request is not None
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
        if acquisition_status in {AcquisitionStatus.FAILED, AcquisitionStatus.NO_RESULT}:
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
        if evaluation_state.evidence_gain == "meaningful_gain":
            return RetrievalResultUtility.USEFUL
        if evaluation_state.evidence_gain == "limited_gain":
            return RetrievalResultUtility.WEAKLY_USEFUL
        return RetrievalResultUtility.NOT_USEFUL

    def _query_fingerprint(self, generated_query: str | None) -> str | None:
        """生成足够稳定且不引入额外持久化依赖的 query 指纹。"""

        if generated_query is None:
            return None
        normalized_query = generated_query.casefold()
        return hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()[:16]
