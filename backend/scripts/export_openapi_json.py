"""Export FastAPI OpenAPI JSON for frontend type generation (openapi-typescript).

Usage (from backend/):
  python scripts/export_openapi_json.py ../frontend/src/lib/generated/openapi.json

The document is normalised so the same source produces the same file on every
toolchain. Newer pydantic releases describe upload fields with
``contentMediaType`` instead of ``format: binary`` and add ``input``/``ctx`` to
``ValidationError``; CI (pinned) emits the older shape, and the freshness check
in CI diffs the committed file byte for byte. Normalising here means a
developer on a newer pydantic no longer produces a "stale" document.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def normalise(node: Any) -> Any:
    """Rewrite toolchain-specific schema details into the canonical (CI) shape."""
    if isinstance(node, dict):
        if node.get("type") == "string" and node.get("contentMediaType") == "application/octet-stream":
            # Keep the key position so the output is byte-identical to the pinned toolchain.
            node = {("format" if k == "contentMediaType" else k): ("binary" if k == "contentMediaType" else v) for k, v in node.items()}
        return {k: normalise(v) for k, v in node.items()}
    if isinstance(node, list):
        return [normalise(v) for v in node]
    return node


def canonical_openapi(document: dict[str, Any]) -> dict[str, Any]:
    document = normalise(document)
    validation_error = document.get("components", {}).get("schemas", {}).get("ValidationError")
    if isinstance(validation_error, dict):
        props = validation_error.get("properties", {})
        for extra in ("input", "ctx"):
            props.pop(extra, None)
    return document


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/export_openapi_json.py <output.json>", file=sys.stderr)
        sys.exit(1)
    out = Path(sys.argv[1])
    from app.main import app  # noqa: PLC0415

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(canonical_openapi(app.openapi()), indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
