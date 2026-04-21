"""One-shot splitter for backend/app/models.py → backend/app/models/*.

Usage:
    cd backend && python ../scripts/split_models.py

Strategy:
- Parse the file into top-level blocks (imports, type aliases, classes).
- Classify each class as 'table' (has `table=True`) or 'schema' (DTO).
- Emit:
    app/models/_types.py    — imports shared by all files + type aliases
    app/models/tables.py    — table=True classes
    app/models/schemas.py   — DTO classes
    app/models/__init__.py  — re-exports so `from ..models import X` works
- Finally move the original models.py out of the way.

Idempotent: if the split has already happened, it refuses to overwrite.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path


BACKEND = Path(__file__).resolve().parent.parent / "backend"
SRC = BACKEND / "app" / "models.py"
PKG = BACKEND / "app" / "models"


def _top_level_blocks(source: str) -> list[tuple[int, int, str]]:
    """Return (start_lineno, end_lineno, kind) for each top-level block."""
    tree = ast.parse(source)
    lines = source.splitlines()
    results: list[tuple[int, int, str]] = []
    for node in tree.body:
        start = node.lineno
        end = getattr(node, "end_lineno", start)
        # Pull leading comments / blank lines that belong to this block.
        back = start - 1
        while back > 0 and (
            not lines[back - 1].strip()
            or lines[back - 1].lstrip().startswith("#")
        ):
            back -= 1
        start = back + 1
        if isinstance(node, ast.ClassDef):
            # Decide table vs schema by looking for `table=True` in the
            # class body's bases (SQLModel uses keyword args) OR decorators.
            kind = "schema"
            src = "\n".join(lines[node.lineno - 1 : end])
            if re.search(r"table\s*=\s*True", src):
                kind = "table"
            results.append((start, end, f"class:{kind}:{node.name}"))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            results.append((start, end, "import"))
        elif isinstance(node, ast.Assign):
            # Top-level type alias e.g. JobStatus = Literal[...]
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if targets:
                results.append((start, end, f"alias:{targets[0]}"))
            else:
                results.append((start, end, "other"))
        else:
            results.append((start, end, f"other:{type(node).__name__}"))
    return results


HEADER_TYPES = '''"""Shared types and type aliases for backend models.

Do not add table classes here. Tables live in ``models/tables.py`` and
request/response DTOs live in ``models/schemas.py``. This module only
hosts the cross-cutting type vocabulary (status literals, plan codes,
job-status strings, etc.).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, field_serializer
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from ..datetime_utils import as_utc_for_json
'''

HEADER_TABLES = '''"""Database tables for the Mainspring backend.

Only SQLModel classes declared with ``table=True`` belong here. Request/
response DTOs live in ``models/schemas.py``.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import field_serializer
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from ..datetime_utils import as_utc_for_json
from ._types import *  # noqa: F401,F403  re-exports aliases for column types
'''

HEADER_SCHEMAS = '''"""Request/response DTOs for the Mainspring API.

These are SQLModel / pydantic models without ``table=True``. They're kept
separate from the database tables in ``models/tables.py`` so API-surface
changes don't force a look at schema migrations.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, field_serializer
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from ..datetime_utils import as_utc_for_json
from ._types import *  # noqa: F401,F403
from .tables import *  # noqa: F401,F403  — DTOs reference table types in hints
'''


def main() -> None:
    if not SRC.exists():
        raise SystemExit(
            f"models.py not found at {SRC}. If the split has already happened,"
            " this script is a no-op."
        )
    if PKG.exists() and PKG.is_dir() and (PKG / "__init__.py").exists():
        raise SystemExit(f"Refusing to overwrite existing package at {PKG}.")

    source = SRC.read_text()
    lines = source.splitlines(keepends=True)
    blocks = _top_level_blocks(source)

    # Split into three buckets.
    alias_blocks: list[str] = []
    table_blocks: list[str] = []
    schema_blocks: list[str] = []

    table_names: list[str] = []
    schema_names: list[str] = []
    alias_names: list[str] = []

    for start, end, kind in blocks:
        chunk = "".join(lines[start - 1 : end])
        if kind == "import":
            # Skip raw imports; the header of each target file carries them.
            continue
        if kind.startswith("alias:"):
            alias_blocks.append(chunk)
            alias_names.append(kind.split(":", 1)[1])
            continue
        if kind.startswith("class:table:"):
            table_blocks.append(chunk)
            table_names.append(kind.split(":", 2)[2])
            continue
        if kind.startswith("class:schema:"):
            schema_blocks.append(chunk)
            schema_names.append(kind.split(":", 2)[2])
            continue
        # Fall-through: keep whatever it was in schemas as the safest bucket.
        schema_blocks.append(chunk)

    PKG.mkdir(parents=True, exist_ok=False)

    (PKG / "_types.py").write_text(
        HEADER_TYPES + "\n\n" + "\n".join(alias_blocks).rstrip() + "\n"
    )
    (PKG / "tables.py").write_text(
        HEADER_TABLES + "\n\n" + "\n".join(table_blocks).rstrip() + "\n"
    )
    (PKG / "schemas.py").write_text(
        HEADER_SCHEMAS + "\n\n" + "\n".join(schema_blocks).rstrip() + "\n"
    )

    # __init__.py: re-export everything so `from ..models import X` keeps working
    # for every existing caller. Order matters: aliases, tables, then schemas.
    init_body = [
        '"""Aggregated re-export module.',
        "",
        "Imports from ``app.models`` (``from ..models import X``) continue to",
        "work unchanged; this package is a thin split of the old",
        "``models.py`` into three files for maintainability. New code should",
        "prefer importing from the specific submodule:",
        "",
        "    from app.models.tables import RepairJob   # DB tables",
        "    from app.models.schemas import RepairJobRead  # API DTOs",
        "    from app.models._types import JobStatus   # shared types",
        '"""',
        "from __future__ import annotations",
        "",
        "from ._types import *  # noqa: F401,F403",
        "from .tables import *  # noqa: F401,F403",
        "from .schemas import *  # noqa: F401,F403",
        "",
    ]
    # Explicit __all__ to keep editors happy.
    all_exports = sorted(set(alias_names + table_names + schema_names))
    init_body.append("__all__ = [")
    for name in all_exports:
        init_body.append(f"    {name!r},")
    init_body.append("]")
    init_body.append("")
    (PKG / "__init__.py").write_text("\n".join(init_body))

    # Finally move the old single-file models.py out of the way by DELETING it
    # — the package directory shadows it.
    SRC.unlink()
    print(f"Split complete: {PKG}")
    print(f"  _types.py:   {len(alias_blocks)} aliases")
    print(f"  tables.py:   {len(table_blocks)} tables")
    print(f"  schemas.py:  {len(schema_blocks)} schemas/DTOs")


if __name__ == "__main__":
    main()
