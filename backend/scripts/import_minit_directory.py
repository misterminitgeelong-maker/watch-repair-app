"""
Import Mister Minit shops + real franchisee owners from an "Organisation Graph"
directory export (an internal Mister Minit IT tool's HTML report).

Unlike scripts/import_minit_shops_from_xlsx.py (which provisions every shop under
the shared HQ login), this reads each shop's real franchisee — name, email,
mobile — and gives them their own owner account: a single ParentAccount-linked
tenant for a single-site franchisee, or their own ParentAccount spanning all
their shops for a multi-site franchisee. Shops with no franchisee on file
(company-owned, or a franchisee record missing an email) fall back to the
shared HQ login, same as the xlsx importer, and are called out in the summary.

New owner accounts get an unusable random placeholder password — nobody can log
in with it. Real credentials come later from a shop-owner invite
(POST /v1/parent-accounts/me/sites/{tenant_id}/invite), which is untouched by
this script.

This never modifies an existing tenant's owner credentials — only fills in
shops/owners/parent accounts that don't exist yet, so it's safe to re-run.

Usage (from repo root):
  cd backend
  python scripts/import_minit_directory.py --input /path/to/directory-export.html
  python scripts/import_minit_directory.py --input export.html --apply --verbose

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
from app.minit_directory_import import plan_directory_import
from app.minit_directory_parser import build_directory, extract_org_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the Mister Minit Organisation Graph directory export")
    parser.add_argument("--input", "-i", required=True, help="Path to the directory export .html file")
    parser.add_argument("--apply", action="store_true", help="Write to the database (default: dry-run only)")
    parser.add_argument("--plan-code", default="booking_only", help="Plan for newly created shop tenants")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(json.dumps({"error": f"File not found: {input_path}"}, indent=2))
        return 1

    if args.verbose:
        print(f"[import] Parsing {input_path}", file=sys.stderr, flush=True)
    html = input_path.read_text(encoding="utf-8")
    graph = extract_org_graph(html)
    directory = build_directory(graph)
    if args.verbose:
        print(
            f"[import] Parsed {len(directory.shops)} shops, {len(directory.franchisees)} franchisees",
            file=sys.stderr,
            flush=True,
        )

    create_db_and_tables()
    with Session(engine) as session:
        summary = plan_directory_import(
            session,
            directory,
            hq_owner_email=settings.minit_hq_owner_email,
            plan_code=args.plan_code,
            apply=args.apply,
        )

    if args.verbose and args.apply:
        print(
            f"[import] Done: tenants={summary.get('created_tenant_count', 0)} "
            f"owners={summary.get('created_owner_count', 0)} "
            f"franchisee_parent_accounts={summary.get('created_franchisee_parent_account_count', 0)}",
            file=sys.stderr,
            flush=True,
        )

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
