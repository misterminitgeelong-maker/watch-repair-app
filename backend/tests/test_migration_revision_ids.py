"""Alembic stores the current revision in alembic_version.version_num, a
VARCHAR(32) on Postgres. A longer revision id passes on SQLite, then fails the
production deploy at startup (it did, on 2026-09-27)."""

import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
_REVISION = re.compile(r"""^revision(?:\s*:\s*str)?\s*=\s*["']([^"']+)["']""", re.M)


def test_every_revision_id_fits_alembic_version_column():
    too_long = []
    for path in sorted(VERSIONS.glob("*.py")):
        match = _REVISION.search(path.read_text(encoding="utf-8"))
        if match and len(match.group(1)) > 32:
            too_long.append(f"{path.name}: {match.group(1)} ({len(match.group(1))} chars)")
    assert not too_long, "Revision ids longer than 32 characters:\n" + "\n".join(too_long)
