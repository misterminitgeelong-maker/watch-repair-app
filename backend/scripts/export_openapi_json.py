"""Export FastAPI OpenAPI JSON for frontend type generation (openapi-typescript).

Usage (from backend/):
  python scripts/export_openapi_json.py ../frontend/src/lib/generated/openapi.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/export_openapi_json.py <output.json>", file=sys.stderr)
        sys.exit(1)
    out = Path(sys.argv[1])
    from app.main import app  # noqa: PLC0415

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
