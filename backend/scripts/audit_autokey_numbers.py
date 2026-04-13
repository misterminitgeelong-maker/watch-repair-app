"""Audit and optionally repair duplicate auto-key job/invoice numbers."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine
from app.models import AutoKeyInvoice, AutoKeyJob


@dataclass
class DuplicateGroup:
    tenant_id: UUID
    value: str
    row_ids: list[UUID]


def _collect_duplicates(rows: list[Any], *, number_attr: str, tenant_attr: str = "tenant_id") -> list[DuplicateGroup]:
    grouped: dict[tuple[UUID, str], list[Any]] = defaultdict(list)
    for row in rows:
        tenant = getattr(row, tenant_attr)
        number = str(getattr(row, number_attr) or "").strip()
        if not number:
            continue
        grouped[(tenant, number)].append(row)

    duplicates: list[DuplicateGroup] = []
    for (tenant_id, value), items in grouped.items():
        if len(items) < 2:
            continue
        items_sorted = sorted(
            items,
            key=lambda r: (
                getattr(r, "created_at", datetime.min) or datetime.min,
                str(getattr(r, "id")),
            ),
        )
        duplicates.append(
            DuplicateGroup(
                tenant_id=tenant_id,
                value=value,
                row_ids=[i.id for i in items_sorted],
            )
        )
    return sorted(duplicates, key=lambda d: (str(d.tenant_id), d.value))


def _extract_prefix_and_seq(value: str, default_prefix: str) -> tuple[str, int]:
    m = re.match(r"^([A-Z]+)-(\d+)$", value.strip().upper())
    if not m:
        return default_prefix, 0
    return m.group(1), int(m.group(2))


def _next_number_for_tenant(rows: list[Any], *, tenant_id: UUID, number_attr: str, prefix: str) -> str:
    max_seq = 0
    for row in rows:
        if getattr(row, "tenant_id") != tenant_id:
            continue
        value = str(getattr(row, number_attr) or "").strip()
        pfx, seq = _extract_prefix_and_seq(value, prefix)
        if pfx == prefix:
            max_seq = max(max_seq, seq)
    return f"{prefix}-{max_seq + 1:05d}"


def _audit_jobs(session: Session, *, fix: bool) -> tuple[int, int]:
    rows = list(session.exec(select(AutoKeyJob)).all())
    duplicates = _collect_duplicates(rows, number_attr="job_number")
    changes = 0
    print(f"\n[AutoKeyJob] duplicate groups: {len(duplicates)}")
    for dup in duplicates:
        print(f"  tenant={dup.tenant_id} number={dup.value} count={len(dup.row_ids)}")
        if not fix:
            continue
        prefix, _ = _extract_prefix_and_seq(dup.value, "AK")
        keep_first = set(dup.row_ids[:1])
        for row in rows:
            if row.id not in dup.row_ids or row.id in keep_first:
                continue
            new_number = _next_number_for_tenant(rows, tenant_id=dup.tenant_id, number_attr="job_number", prefix=prefix)
            print(f"    fix job {row.id}: {row.job_number} -> {new_number}")
            row.job_number = new_number
            changes += 1
    return len(duplicates), changes


def _audit_invoices(session: Session, *, fix: bool) -> tuple[int, int]:
    rows = list(session.exec(select(AutoKeyInvoice)).all())
    duplicates = _collect_duplicates(rows, number_attr="invoice_number")
    changes = 0
    print(f"\n[AutoKeyInvoice] duplicate groups: {len(duplicates)}")
    for dup in duplicates:
        print(f"  tenant={dup.tenant_id} number={dup.value} count={len(dup.row_ids)}")
        if not fix:
            continue
        prefix, _ = _extract_prefix_and_seq(dup.value, "AKI")
        keep_first = set(dup.row_ids[:1])
        for row in rows:
            if row.id not in dup.row_ids or row.id in keep_first:
                continue
            new_number = _next_number_for_tenant(rows, tenant_id=dup.tenant_id, number_attr="invoice_number", prefix=prefix)
            print(f"    fix invoice {row.id}: {row.invoice_number} -> {new_number}")
            row.invoice_number = new_number
            changes += 1
    return len(duplicates), changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and optionally fix duplicate auto-key numbers.")
    parser.add_argument("--fix", action="store_true", help="Apply repairs for duplicate numbers.")
    args = parser.parse_args()

    with Session(engine) as session:
        job_groups, job_changes = _audit_jobs(session, fix=args.fix)
        inv_groups, inv_changes = _audit_invoices(session, fix=args.fix)
        if args.fix and (job_changes or inv_changes):
            session.commit()
            print(f"\nApplied fixes: jobs={job_changes}, invoices={inv_changes}")
        elif args.fix:
            print("\nNo fixes needed.")

    total_groups = job_groups + inv_groups
    print(f"\nTotal duplicate groups: {total_groups}")
    return 1 if (total_groups > 0 and not args.fix) else 0


if __name__ == "__main__":
    raise SystemExit(main())
