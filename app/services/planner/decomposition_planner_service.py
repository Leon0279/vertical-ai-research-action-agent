"""Planning and decomposition implementation."""

from __future__ import annotations

import re

from app.domain.enums import PlanningDepth, TaskType
from app.domain.models import ExecutionContext
from app.services.planner.contracts.decomposition_planner_protocol import DecompositionPlannerProtocol


class DecompositionPlannerService(DecompositionPlannerProtocol):
    """负责处理拆解规划器相关业务逻辑的服务。

Produce deterministic MVP planning artifacts."""

    async def plan(self, context: ExecutionContext) -> None:
        state = context.running_state
        task_type = self._task_type_from_state(state.task_type)
        planning_depth = self._planning_depth_for(context=context, task_type=task_type)
        state.planning_depth = planning_depth

        if planning_depth == PlanningDepth.NONE:
            state.plan = []
            state.sub_questions = []
            state.comparison_candidates = []
            state.initial_evidence_strategy = []
            return

        objective = state.user_goal or state.original_query
        comparison_candidates = self._comparison_candidates_for(
            task_type=task_type,
            query=state.original_query,
        )
        state.comparison_candidates = comparison_candidates
        state.plan = self._plan_for(
            task_type=task_type,
            objective=objective,
            planning_depth=planning_depth,
            context=context,
        )
        state.sub_questions = self._sub_questions_for(
            task_type=task_type,
            objective=objective,
            comparison_candidates=comparison_candidates,
            context=context,
        )
        state.initial_evidence_strategy = self._initial_evidence_strategy_for(
            task_type=task_type,
            comparison_candidates=comparison_candidates,
            context=context,
        )
        state.information_gaps = self._merge_unique(
            state.information_gaps,
            self._information_gaps_for(
                task_type=task_type,
                comparison_candidates=comparison_candidates,
                context=context,
            ),
        )

    def _task_type_from_state(self, task_type: str | None) -> TaskType:
        if not task_type:
            return TaskType.TOPIC_EXPLORATION
        try:
            return TaskType(task_type)
        except ValueError:
            return TaskType.TOPIC_EXPLORATION

    def _planning_depth_for(
        self,
        *,
        context: ExecutionContext,
        task_type: TaskType,
    ) -> PlanningDepth:
        policy = context.running_state.execution_policy
        if policy is not None:
            return policy.planning_depth

        if task_type in {
            TaskType.COMPARISON,
            TaskType.RECOMMENDATION,
            TaskType.ACTION_PLANNING,
        }:
            return PlanningDepth.MEDIUM
        return PlanningDepth.SHALLOW

    def _plan_for(
        self,
        *,
        task_type: TaskType,
        objective: str,
        planning_depth: PlanningDepth,
        context: ExecutionContext,
    ) -> list[str]:
        state = context.running_state
        plan = [
            f"Objective: {objective}",
            f"Planning depth: {planning_depth.value}",
        ]
        if state.project_context_summary:
            plan.append("Ground the task in the current project context and constraints.")

        if task_type == TaskType.COMPARISON:
            plan.extend(
                [
                    "Clarify the comparison criteria that matter for this task.",
                    "Compare the candidate options against the project constraints.",
                    "Summarize tradeoffs and unresolved evidence gaps.",
                ]
            )
        elif task_type == TaskType.RECOMMENDATION:
            plan.extend(
                [
                    "Ground the recommendation in the current project stage and bottlenecks.",
                    "Compare viable options before selecting a direction.",
                    "Produce a recommendation with rationale and follow-up actions.",
                ]
            )
        elif task_type == TaskType.ACTION_PLANNING:
            plan.extend(
                [
                    "Clarify the target outcome and immediate execution boundary.",
                    "Identify dependencies, blockers, and sequencing constraints.",
                    "Produce concrete next steps that can be acted on.",
                ]
            )
        elif task_type == TaskType.TRACKING:
            plan.extend(
                [
                    "Identify what status or change needs to be tracked.",
                    "Check the latest known project action status and open questions.",
                    "Summarize updates, risks, and follow-up needs.",
                ]
            )
        else:
            plan.extend(
                [
                    "Clarify the key concepts and boundaries of the topic.",
                    "Collect representative evidence or examples.",
                    "Summarize the practical implications for the user goal.",
                ]
            )
        return plan

    def _sub_questions_for(
        self,
        *,
        task_type: TaskType,
        objective: str,
        comparison_candidates: list[str],
        context: ExecutionContext,
    ) -> list[str]:
        state = context.running_state
        if task_type == TaskType.COMPARISON:
            if len(comparison_candidates) >= 2:
                return [
                    "Which criteria should be used to compare the candidate options?",
                    *[
                        f"What are the strengths, weaknesses, and risks of {candidate}?"
                        for candidate in comparison_candidates
                    ],
                    "Which option fits the current constraints best?",
                ]
            return [
                "What options need to be compared?",
                "Which criteria should be used to compare them?",
                "What evidence would make the tradeoff clear?",
            ]

        if task_type == TaskType.RECOMMENDATION:
            questions = [
                "What decision does the user need to make in this run?",
                "Which options are viable under the current constraints?",
                "What rationale would support the final recommendation?",
            ]
            if state.current_bottleneck_summary:
                questions.insert(1, "How does the current bottleneck affect the recommendation?")
            return questions

        if task_type == TaskType.ACTION_PLANNING:
            return [
                "What outcome should the action plan achieve?",
                "What dependencies or blockers must be handled first?",
                "What are the next concrete steps and ownership boundaries?",
            ]

        if task_type == TaskType.TRACKING:
            return [
                "What changed since the last known status?",
                "Which open actions or risks still need attention?",
                "What follow-up is needed after this update?",
            ]

        if context.running_state.planning_depth == PlanningDepth.SHALLOW:
            return []
        return [
            f"What are the main concepts needed to address: {objective}?",
            "What evidence or examples would make the explanation reliable?",
        ]

    def _initial_evidence_strategy_for(
        self,
        *,
        task_type: TaskType,
        comparison_candidates: list[str],
        context: ExecutionContext,
    ) -> list[str]:
        state = context.running_state
        strategy: list[str] = []
        if state.execution_policy is not None:
            strategy.append(
                f"Use {state.execution_policy.evidence_strategy} as the initial evidence posture."
            )

        if state.active_decision_summary:
            strategy.append("Review active project decisions before shaping the answer.")
        if state.current_action_status and task_type in {
            TaskType.ACTION_PLANNING,
            TaskType.TRACKING,
        }:
            strategy.append("Use current action status to anchor execution-oriented outputs.")

        if task_type == TaskType.COMPARISON:
            if comparison_candidates:
                strategy.append("Gather comparable evidence for each identified candidate.")
            strategy.append("Prioritize evidence that clarifies tradeoffs under constraints.")
        elif task_type == TaskType.RECOMMENDATION:
            strategy.append("Prioritize decision-support evidence and known project constraints.")
            strategy.append("Look for evidence that can justify concrete follow-up actions.")
        elif task_type == TaskType.ACTION_PLANNING:
            strategy.append("Prioritize dependencies, blockers, sequencing, and feasibility signals.")
        elif task_type == TaskType.TRACKING:
            strategy.append("Prioritize fresh status signals and unresolved follow-up items.")
        else:
            strategy.append("Prioritize concise background knowledge and representative examples.")

        if context.supplemental_context.research_support:
            strategy.append("Use selected research support before broadening retrieval.")
        return self._merge_unique([], strategy)

    def _information_gaps_for(
        self,
        *,
        task_type: TaskType,
        comparison_candidates: list[str],
        context: ExecutionContext,
    ) -> list[str]:
        state = context.running_state
        gaps: list[str] = []
        if task_type in {TaskType.COMPARISON, TaskType.RECOMMENDATION} and not comparison_candidates:
            gaps.append("Comparison candidates are not explicit enough for structured comparison.")
        if task_type == TaskType.RECOMMENDATION and not (
            state.project_context_summary or context.supplemental_context.project_support
        ):
            gaps.append("Project context is limited for recommendation grounding.")
        if task_type in {TaskType.ACTION_PLANNING, TaskType.TRACKING} and not state.current_action_status:
            gaps.append("Current action status is not available.")
        return gaps

    def _comparison_candidates_for(
        self,
        *,
        task_type: TaskType,
        query: str,
    ) -> list[str]:
        if task_type not in {TaskType.COMPARISON, TaskType.RECOMMENDATION}:
            return []

        for separator in (" versus ", " vs ", " or "):
            if separator in query.lower():
                return self._split_candidates(query=query, separator=separator)
        return []

    def _split_candidates(self, *, query: str, separator: str) -> list[str]:
        pattern = re.compile(re.escape(separator), re.IGNORECASE)
        parts = pattern.split(query, maxsplit=1)
        if len(parts) != 2:
            return []
        candidates = [self._clean_candidate(part) for part in parts]
        return [candidate for candidate in candidates if candidate]

    def _clean_candidate(self, value: str) -> str:
        candidate = value.strip(" ?.,:;\"'")
        lowered = candidate.lower()
        for prefix in (
            "should i prioritize ",
            "should we prioritize ",
            "should i choose ",
            "should we choose ",
            "compare ",
            "choose between ",
            "prioritize ",
        ):
            if lowered.startswith(prefix):
                candidate = candidate[len(prefix) :]
                lowered = candidate.lower()
                break
        for boundary in (" for ", " under ", " in ", " given "):
            index = lowered.find(boundary)
            if index > 0:
                candidate = candidate[:index]
                break
        return candidate.strip(" ?.,:;\"'")

    def _merge_unique(self, existing: list[str], additions: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for item in [*existing, *additions]:
            normalized = item.strip()
            if normalized and normalized not in seen:
                merged.append(normalized)
                seen.add(normalized)
        return merged
