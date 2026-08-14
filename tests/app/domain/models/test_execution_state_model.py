"""Execution context migration guard tests."""

from pathlib import Path


def test_runtime_components_no_longer_import_execution_state() -> None:
    app_root = Path("app")
    checked_roots = [
        app_root / "orchestration",
        app_root / "services",
    ]

    offenders = []
    for root in checked_roots:
        for path in root.rglob("*.py"):
            if "ExecutionState" in path.read_text():
                offenders.append(str(path))

    assert offenders == []
