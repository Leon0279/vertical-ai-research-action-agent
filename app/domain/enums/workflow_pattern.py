"""Workflow routing pattern enums."""

from enum import StrEnum


class WorkflowPattern(StrEnum):
    """定义工作流模式的可选枚举值。

Execution patterns selected by the workflow router."""

    TOPIC_EXPLORATION = "TOPIC_EXPLORATION_FLOW"
    COMPARISON = "COMPARISON_FLOW"
    RECOMMENDATION = "RECOMMENDATION_FLOW"
    ACTION_PLANNING = "ACTION_PLANNING_FLOW"
    TRACKING = "TRACKING_FLOW"
