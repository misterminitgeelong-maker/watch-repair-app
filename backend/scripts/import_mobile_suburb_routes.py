"""
Bulk-import generated mobile suburb routes into MobileSuburbRoute.

Usage (from backend/):
  python scripts/import_mobile_suburb_routes.py --input seed/minit_mobile_territory_routes_au_2026.json
  python scripts/import_mobile_suburb_routes.py --input seed/minit_mobile_territory_routes_au_2026.json --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select

from app.config import settings
from app.database import create_db_and_tables, engine
from app.minit_mobile_territory_import import import_mobile_suburb_routes, load_territory_routes_seed
from app.models import ParentAccount


def import_routes_from_file(path: Path, *, apply: bool, verbose: bool = False) -> int:
    if not path.is_file():
        print(json.dumps({"error": f"File not found: {path}"}, indent=2))
        return 1

    create_db_and_tables()
    routes, operators = load_territory_routes_seed(path)
    email = settings.minit_hq_owner_email.strip().lower()
    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == email)).first()
        if not parent:
            print(json.dumps({"error": f"Parent account not found for {email}"}, indent=2))
            return 1
        summary = import_mobile_suburb_routes(
            session,
            parent_id=parent.id,
            routes=routes,
            operators=operators,
            apply=apply,
        )
    if verbose:
        print(json.dumps(summary, indent=2), file=sys.stderr)
    else:
        print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Import generated mobile suburb routes")
    parser.add_argument("--input", "-i", required=True, help="Territory JSON from generate script")
    parser.add_argument("--apply", action="store_true", help="Write routes to database")
    parser.add_argument("--replace-existing", action="store_true", help="Delete existing routes before import")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    return import_routes_from_file(Path(args.input), apply=args.apply, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
