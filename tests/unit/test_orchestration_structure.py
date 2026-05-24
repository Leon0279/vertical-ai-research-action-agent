"""Structure tests for orchestration internals."""

import inspect

from app.orchestration import research_action_pipeline


def test_pipeline_module_no_stage_imports() -> None:
    source = inspect.getsource(research_action_pipeline)
    assert "from app.orchestration import stage_" not in source
    assert "await stage_" not in source

