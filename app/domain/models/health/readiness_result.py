"""Readiness result domain model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReadinessCheckStatus = Literal["ok", "error"]


class ReadinessResult(BaseModel):
    """Represent the safe aggregate status of runtime dependencies."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"] = Field(
        description="Aggregate readiness status for the API process."
    )
    checks: dict[str, ReadinessCheckStatus] = Field(
        description="Allow-listed dependency checks without connection details."
    )
