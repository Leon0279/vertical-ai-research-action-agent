"""Export the FastAPI OpenAPI document used by the frontend code generator."""

from __future__ import annotations

import json
from pathlib import Path

from app.api.app import app


def main() -> None:
    """Write a deterministic, human-readable OpenAPI snapshot."""

    output_path = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"
    output_path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI schema written to {output_path}")


if __name__ == "__main__":
    main()
