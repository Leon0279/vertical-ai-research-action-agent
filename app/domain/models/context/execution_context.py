"""Complete execution environment used for stage input projection."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models.context.running_state import RunningState
from app.domain.models.context.runtime_context import RuntimeContext
from app.domain.models.context.supplemental_context import SupplementalContext


class ExecutionContext(BaseModel):
    """Complete execution environment used for stage input projection."""

    running_state: RunningState
    supplemental_context: SupplementalContext = Field(default_factory=SupplementalContext)
    runtime_context: RuntimeContext
