"""Retrieval acquisition outcome enums."""

from enum import StrEnum


class AcquisitionStatus(StrEnum):
    """Tool/family retrieval acquisition 的共享执行状态。"""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    NO_RESULT = "no_result"
    FAILED = "failed"
