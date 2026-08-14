"""Final response assembly skeleton."""

from app.domain.enums.task_type import TaskType
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models import ActionItem, ExecutionContext, RunningState, StructuredOutput
from app.services.output.contracts.response_assembler_protocol import ResponseAssemblerProtocol


class ResponseAssemblerService(ResponseAssemblerProtocol):
    """负责处理响应组装器相关业务逻辑的服务。

Assemble final structured output from execution context."""

    async def assemble(self, context: ExecutionContext) -> StructuredOutput:
        state = context.running_state
        runtime_context = context.runtime_context
        task_type = self._task_type_from_state(state.task_type)
        return StructuredOutput(
            trace_id=runtime_context.request_id,
            task_type=task_type,
            workflow_pattern=state.workflow_pattern or self._workflow_pattern_from_task_type(task_type),
            answer=state.final_answer or self._fallback_answer(state),
            summary=self._summary(state.final_summary, state.final_answer),
            recommendation=state.final_recommendation,
            action_items=[ActionItem(title=item) for item in state.action_items],
            citations=state.citations,
            confidence=self._confidence_to_score(state.confidence),
            caveats=state.caveats,
            stage_history=runtime_context.stage_history,
            metadata={
                "session_id": runtime_context.session_id,
                "session_id_generated": runtime_context.session_id_generated,
            },
        )

    def _task_type_from_state(self, task_type: str | None) -> TaskType:
        if not task_type:
            return TaskType.TOPIC_EXPLORATION
        return TaskType(task_type)

    def _workflow_pattern_from_task_type(self, task_type: TaskType) -> WorkflowPattern:
        return {
            TaskType.TOPIC_EXPLORATION: WorkflowPattern.TOPIC_EXPLORATION,
            TaskType.COMPARISON: WorkflowPattern.COMPARISON,
            TaskType.RECOMMENDATION: WorkflowPattern.RECOMMENDATION,
            TaskType.ACTION_PLANNING: WorkflowPattern.ACTION_PLANNING,
            TaskType.TRACKING: WorkflowPattern.TRACKING,
        }[task_type]

    def _confidence_to_score(self, confidence: str | None) -> float | None:
        if confidence is None:
            return None
        return {
            "low": 0.2,
            "medium": 0.5,
            "high": 0.8,
        }.get(confidence.lower())

    def _fallback_answer(self, state: RunningState) -> str:
        if state.final_recommendation and state.final_recommendation.strip():
            return state.final_recommendation.strip()
        if state.evidence_summary and state.evidence_summary.strip():
            return (
                "当前尚未生成完整最终答案，但已有研究摘要可供参考："
                f"{state.evidence_summary.strip()}"
            )
        return "当前尚未形成可展示的完整最终答案。"

    def _summary(self, final_summary: str | None, final_answer: str | None) -> str:
        if final_summary and final_summary.strip():
            return final_summary.strip()
        if final_answer and final_answer.strip():
            return self._truncate_summary(final_answer.strip())
        return "当前尚未形成最终答案摘要。"

    def _truncate_summary(self, value: str, max_length: int = 160) -> str:
        text = " ".join(value.split())
        if len(text) <= max_length:
            return text
        return text[: max_length - 1].rstrip() + "..."
