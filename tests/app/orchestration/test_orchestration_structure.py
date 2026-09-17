"""Structure tests for orchestration internals."""

import ast
import inspect
from pathlib import Path

from app.orchestration import research_action_pipeline


def test_pipeline_module_no_stage_imports() -> None:
    source = inspect.getsource(research_action_pipeline)
    assert "from app.orchestration import stage_" not in source
    assert "await stage_" not in source


def test_routes_and_orchestration_do_not_construct_application_dependencies() -> None:
    project_root = Path(__file__).resolve().parents[3]
    paths = [
        *sorted((project_root / "app" / "api" / "routes").glob("*.py")),
        project_root / "app" / "orchestration" / "research_action_pipeline.py",
        project_root / "app" / "orchestration" / "pipeline_dependencies.py",
    ]

    forbidden_suffixes = ("Service", "Client", "Store", "Pipeline")
    violations: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                callable_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                callable_name = node.func.attr
            else:
                continue
            if callable_name.endswith(forbidden_suffixes):
                violations.append(f"{path.relative_to(project_root)}:{node.lineno}:{callable_name}")

    assert violations == []
