"""
Create Mister Minit HQ parent account and pilot sites (idempotent).

Uses MINIT_* environment variables (see docs/MINIT_ONBOARDING.md).

  cd backend
  python scripts/seed_minit_pilot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlmodel import Session

from app.config import settings
from app.database import create_db_and_tables, engine
from app.minit_provision import ensure_minit_pilot_account


def main() -> int:
    create_db_and_tables()
    with Session(engine) as session:
        result = ensure_minit_pilot_account(
            session,
            parent_name=settings.minit_parent_account_name,
            hq_tenant_slug=settings.minit_hq_tenant_slug.strip().lower(),
            hq_tenant_name=settings.minit_hq_tenant_name,
            hq_owner_email=settings.minit_hq_owner_email,
            hq_owner_password=settings.minit_hq_owner_password,
        )
    print(
        json.dumps(
            {
                "parent_account_id": str(result.parent_account_id),
                "parent_account_name": result.parent_account_name,
                "hq_tenant_slug": result.hq_tenant_slug,
                "hq_owner_email": result.hq_owner_email,
                "hq_owner_password": settings.minit_hq_owner_password,
                "created_tenant_slugs": result.created_tenant_slugs,
                "skipped_shop_numbers": result.skipped_shop_numbers,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
