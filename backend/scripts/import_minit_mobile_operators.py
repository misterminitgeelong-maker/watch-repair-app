"""
Bulk-import Mister Minit mobile operators from seed JSON + TSS metadata.

Default seed: backend/seed/minit_mobile_operators_2026.json
Default TSS workbook (local only — do not commit):
  c:\\Users\\samme\\Downloads\\TSS Dec25 Report (1).xlsx

Usage (from repo root):
  cd backend
  python scripts/import_minit_mobile_operators.py
  python scripts/import_minit_mobile_operators.py --check-db
  python scripts/import_minit_mobile_operators.py --apply --verbose
  python scripts/import_minit_mobile_operators.py --seed-pilot --apply
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
from app.minit_mobile_operators import (
    DEFAULT_OPERATORS_SEED_PATH,
    index_tss_shops_by_number,
    load_mobile_operators_seed,
    resolve_mobile_operators,
)
from app.minit_provision import ensure_minit_pilot_account, import_minit_mobile_operators
from app.minit_shops import DEFAULT_TSS_XLSX_PATH, parse_minit_shops_xlsx


def _progress_logger(verbose: bool):
    if not verbose:
        return None

    def on_progress(done: int, total: int, phase: str) -> None:
        print(f"[import-operators] {done}/{total} ({phase})", file=sys.stderr, flush=True)

    return on_progress


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Mister Minit mobile operators")
    parser.add_argument(
        "--seed",
        default=str(DEFAULT_OPERATORS_SEED_PATH),
        help="Path to operator seed JSON",
    )
    parser.add_argument(
        "--tss",
        "-i",
        default=DEFAULT_TSS_XLSX_PATH,
        help="Path to TSS / shop-list .xlsx for area/region metadata",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create operator tenants (default: dry-run only)",
    )
    parser.add_argument(
        "--plan-code",
        default="basic_auto_key",
        help="Plan for imported operators (default: basic_auto_key)",
    )
    parser.add_argument(
        "--seed-pilot",
        action="store_true",
        help="Ensure HQ + pilot sites before import (uses MINIT_* env settings)",
    )
    parser.add_argument(
        "--check-db",
        action="store_true",
        help="Query DB for duplicate operator shop numbers (dry-run; requires database)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log progress to stderr during --apply",
    )
    args = parser.parse_args()

    seed_path = Path(args.seed)
    if not seed_path.is_file():
        print(json.dumps({"error": f"Seed file not found: {seed_path}"}, indent=2))
        return 1

    tss_path = Path(args.tss)
    if not tss_path.is_file():
        print(json.dumps({"error": f"TSS file not found: {tss_path}"}, indent=2))
        return 1

    if args.verbose:
        print(f"[import-operators] Loading seed {seed_path}", file=sys.stderr, flush=True)
    seeds = load_mobile_operators_seed(seed_path)

    if args.verbose:
        print(f"[import-operators] Parsing TSS {tss_path}", file=sys.stderr, flush=True)
    tss_shops = parse_minit_shops_xlsx(tss_path)
    tss_by_number = index_tss_shops_by_number(tss_shops)
    operators, resolve_errors = resolve_mobile_operators(seeds, tss_by_number)

    if resolve_errors:
        print(
            json.dumps(
                {
                    "error": "Failed to resolve one or more operators against TSS",
                    "resolve_errors": resolve_errors,
                },
                indent=2,
            )
        )
        return 1

    if not args.apply and not args.check_db and not args.seed_pilot:
        summary = {
            "dry_run": True,
            "parse_only": True,
            "seed_path": str(seed_path),
            "tss_path": str(tss_path),
            "operator_count": len(operators),
            "would_create_count": len(operators),
            "note": "Parse-only dry-run (no database). Re-run with --check-db after pilot seed.",
            "sample": [
                {
                    "shop_number": op.shop_number,
                    "name": op.tenant_name,
                    "slug": op.tenant_slug,
                    "dispatch_phone": op.dispatch_phone,
                    "area": op.tss.area,
                    "region": op.tss.region,
                    "tss_name": op.tss.name,
                }
                for op in operators[:10]
            ],
        }
        print(json.dumps(summary, indent=2))
        return 0

    create_db_and_tables()

    with Session(engine) as session:
        if args.seed_pilot:
            if args.verbose:
                print("[import-operators] Ensuring Minit HQ + pilot sites", file=sys.stderr, flush=True)
            ensure_minit_pilot_account(
                session,
                parent_name=settings.minit_parent_account_name,
                hq_tenant_slug=settings.minit_hq_tenant_slug.strip().lower(),
                hq_tenant_name=settings.minit_hq_tenant_name,
                hq_owner_email=settings.minit_hq_owner_email,
                hq_owner_password=settings.minit_hq_owner_password,
            )

        summary = import_minit_mobile_operators(
            session,
            parent_name=settings.minit_parent_account_name,
            hq_owner_email=settings.minit_hq_owner_email,
            operators=operators,
            plan_code=args.plan_code,
            apply=args.apply,
            on_progress=_progress_logger(args.verbose),
        )

    summary["seed_path"] = str(seed_path)
    summary["tss_path"] = str(tss_path)
    summary["operator_count"] = len(operators)
    summary["dry_run"] = not args.apply
    if args.verbose and args.apply:
        print(
            f"[import-operators] Done: created={summary.get('created_count', 0)} "
            f"updated={summary.get('updated_count', 0)} "
            f"skipped={summary.get('skipped_count', summary.get('would_skip_count', 0))}",
            file=sys.stderr,
            flush=True,
        )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
