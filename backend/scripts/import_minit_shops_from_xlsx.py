"""
Bulk-import Mister Minit retail shops from a TSS / shop-list Excel export.

Default workbook (local only — do not commit):
  c:\\Users\\samme\\Downloads\\TSS Dec25 Report (1).xlsx

Usage (from repo root):
  cd backend
  python scripts/import_minit_shops_from_xlsx.py
  python scripts/import_minit_shops_from_xlsx.py --input "C:/path/to/TSS Dec25 Report (1).xlsx"
  python scripts/import_minit_shops_from_xlsx.py --apply   # writes tenants (pilot seed / HQ must exist)

Dry-run is the default. Output is JSON summary on stdout.
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
from app.minit_provision import ensure_minit_pilot_account, import_minit_shops
from app.minit_shops import DEFAULT_TSS_XLSX_PATH, parse_minit_shops_xlsx


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Mister Minit shops from TSS xlsx")
    parser.add_argument(
        "--input",
        "-i",
        default=DEFAULT_TSS_XLSX_PATH,
        help="Path to TSS / shop-list .xlsx",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create tenants (default: dry-run only)",
    )
    parser.add_argument(
        "--plan-code",
        default="booking_only",
        help="Plan for imported retail shops (default: booking_only)",
    )
    parser.add_argument(
        "--seed-pilot",
        action="store_true",
        help="Ensure HQ + pilot shops before import (uses MINIT_* env settings)",
    )
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Query DB for duplicate shop numbers (dry-run only; requires migrated database)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(json.dumps({"error": f"File not found: {input_path}"}, indent=2))
        return 1

    shops = parse_minit_shops_xlsx(input_path)

    if not args.apply and not args.check_db and not args.seed_pilot:
        summary = {
            "dry_run": True,
            "parse_only": True,
            "input_path": str(input_path),
            "parsed_shop_count": len(shops),
            "would_create_count": len(shops),
            "would_skip_count": 0,
            "note": "Parse-only dry-run (no database). Re-run with --check-db after pilot seed for duplicate detection.",
            "sample": [
                {
                    "shop_number": s.shop_number,
                    "name": s.name,
                    "slug": f"minit-{s.shop_number}",
                    "business_address": s.business_address,
                }
                for s in shops[:10]
            ],
        }
        print(json.dumps(summary, indent=2))
        return 0

    create_db_and_tables()

    with Session(engine) as session:
        if args.seed_pilot:
            ensure_minit_pilot_account(
                session,
                parent_name=settings.minit_parent_account_name,
                hq_tenant_slug=settings.minit_hq_tenant_slug.strip().lower(),
                hq_tenant_name=settings.minit_hq_tenant_name,
                hq_owner_email=settings.minit_hq_owner_email,
                hq_owner_password=settings.minit_hq_owner_password,
            )

        summary = import_minit_shops(
            session,
            parent_name=settings.minit_parent_account_name,
            hq_owner_email=settings.minit_hq_owner_email,
            shops=shops,
            plan_code=args.plan_code,
            apply=args.apply,
        )

    summary["input_path"] = str(input_path)
    summary["parsed_shop_count"] = len(shops)
    summary["dry_run"] = not args.apply
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
