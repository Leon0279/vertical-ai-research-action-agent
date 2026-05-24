"""Importability tests for architecture skeleton."""

from app.api.app import app
from app.orchestration.research_action_pipeline import ResearchActionPipeline, build_default_pipeline


def test_app_importable() -> None:
    assert app.title


def test_pipeline_importable() -> None:
    pipeline = build_default_pipeline()
    assert isinstance(pipeline, ResearchActionPipeline)


def test_pipeline_exposes_private_stage_methods() -> None:
    pipeline = build_default_pipeline()
    for method_name in (
        "_request_intake",
        "_task_interpretation",
        "_context_memory_load",
        "_workflow_routing",
        "_planning",
        "_research",
        "_conclusion",
        "_memory_writeback",
        "_output",
    ):
        assert hasattr(pipeline, method_name)
