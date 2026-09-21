"""
Fill in real franchisee contact details for Mister Minit shops that are still
sharing the HQ login, from an "Organisation Graph" directory export.

scripts/import_minit_directory.py only sets an owner identity on shops it
creates. Shops loaded by scripts/import_minit_shops_from_xlsx.py, or added by
hand in HQ, hold a copy of the HQ login instead — so every later directory
import skips them and their contact details never arrive. That leaves HQ with
nobody to send a shop-owner invite to.

This closes that gap and only that gap. A shop qualifies only when its owner
row is still literally the HQ login, which is the one case where there are no
real credentials to overwrite. A shop whose owner is a real person — claimed by
invite, edited by hand, or backfilled by an earlier run — is left alone, so
this is safe to re-run.

Passwords are not touched. Completing a shop-owner invite
(POST /v1/parent-accounts/me/sites/{tenant_id}/invite) is what sets real
credentials, exactly as before.

There is an HQ endpoint for this too
(POST /v1/parent-accounts/me/backfill-shop-owner-contacts), but a whole network
in one request can outlast a reverse proxy's read timeout. This script talks to
the database directly and has no such limit, so prefer it for a full run.

Usage (from repo root):
  cd backend
  python scripts/backfill_shop_owner_contacts.py --input /path/to/directory-export.html
  python scripts/backfill_shop_owner_contacts.py --input export.html --apply --verbose

Dry-run is the default. Output is a JSON summary on stdout.

Do not commit the directory export file itself — it carries real franchisee
names, emails, and mobile numbers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session

from app.config import settings
from app.database import create_db_and_tables, engine
from app.minit_directory_import import backfill_shared_login_owners
from app.minit_directory_parser import build_directory, extract_org_graph


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill franchisee contact details onto shops still sharing the HQ login"
    )
    parser.add_argument("--input", "-i", required=True, help="Path to the directory export .html file")
    parser.add_argument("--apply", action="store_true", help="Write to the database (default: dry-run only)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(json.dumps({"error": f"File not found: {input_path}"}, indent=2))
        return 1

    if args.verbose:
        print(f"[backfill] Parsing {input_path}", file=sys.stderr, flush=True)
    directory = build_directory(extract_org_graph(input_path.read_text(encoding="utf-8")))
    if args.verbose:
        print(
            f"[backfill] Parsed {len(directory.shops)} shops, {len(directory.franchisees)} franchisees",
            file=sys.stderr,
            flush=True,
        )

    create_db_and_tables()
    with Session(engine) as session:
        summary = backfill_shared_login_owners(
            session,
            directory,
            hq_owner_email=settings.minit_hq_owner_email,
            apply=args.apply,
        )

    if args.verbose:
        verb = "Updated" if args.apply else "Would update"
        print(f"[backfill] {verb} {summary.get('matched_count', 0)} shops", file=sys.stderr, flush=True)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
