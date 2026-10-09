"""HQ view of shoe repairs across every shop in the network.

For HQs with the ``shoe`` module on. Read-only: HQ sees where repairs are, how
long they take and what is billed; shops keep running their own tickets.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, select

from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context
from ..hq_access import require_hq
from ..models import (
    NETWORK_ROLE_HQ,
    Customer,
    Region,
    Shoe,
    ShoeJobStatusHistory,
    ShoeRepairJob,
    ShoeRepairJobItem,
    Tenant,
)
from ..parent_network import sites_for_parent
from ..phone_utils import normalize_phone
from .parent_accounts import _parent_for_read

router = APIRouter(prefix="/v1/parent-accounts", tags=["parent-shoe-operations"])

#: A repair is finished for HQ's purposes once the customer has it back or declined.
_CLOSED_STATUSES = ("collected", "no_go")
_READY_STATUSES = ("completed", "awaiting_collection")


def _parse(value: str | None, name: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{name} must be ISO-8601") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _shops(session: Session, parent_id: UUID) -> dict[UUID, tuple[Tenant, str | None]]:
    """Shops in the network (HQ itself excluded) with their region name."""
    sites = [s for s in sites_for_parent(session, parent_id) if s.network_role != NETWORK_ROLE_HQ]
    tenants = {t.id: t for t in session.exec(select(Tenant).where(col(Tenant.id).in_([s.tenant_id for s in sites]))).all()} if sites else {}
    region_ids = {s.region_id for s in sites if s.region_id}
    regions = {r.id: r.name for r in session.exec(select(Region).where(col(Region.id).in_(region_ids))).all()} if region_ids else {}
    return {s.tenant_id: (tenants[s.tenant_id], regions.get(s.region_id)) for s in sites if s.tenant_id in tenants}


@router.get("/me/operations/shoe-jobs/summary")
def shoe_jobs_summary(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    require_hq(auth, session, "shoe")
    _, parent, _ = _parent_for_read(session, auth)
    shops = _shops(session, parent.id)
    start, end = _parse(from_date, "from_date"), _parse(to_date, "to_date")
    now = datetime.now(timezone.utc)

    rows: dict[UUID, dict] = {
        tid: {
            "tenant_id": str(tid), "tenant_name": t.name, "tenant_slug": t.slug, "region": region,
            "opened": 0, "active": 0, "ready_to_collect": 0, "collected": 0, "billed_cents": 0,
            "avg_turnaround_days": None, "oldest_active_days": None,
        }
        for tid, (t, region) in shops.items()
    }
    status_counts: dict[str, int] = defaultdict(int)
    turnaround: dict[UUID, list[float]] = defaultdict(list)
    if shops:
        ids = list(shops)
        jobs = session.exec(select(ShoeRepairJob).where(col(ShoeRepairJob.tenant_id).in_(ids))).all()
        in_period = [j for j in jobs if (start is None or _utc(j.created_at) >= start) and (end is None or _utc(j.created_at) <= end)]
        for job in jobs:
            row = rows[job.tenant_id]
            if job.status not in _CLOSED_STATUSES:
                row["active"] += 1
                age = (now - _utc(job.created_at)).days
                row["oldest_active_days"] = max(row["oldest_active_days"] or 0, age)
            if job.status in _READY_STATUSES:
                row["ready_to_collect"] += 1
        for job in in_period:
            row = rows[job.tenant_id]
            row["opened"] += 1
            status_counts[job.status] += 1
            if job.status == "collected":
                row["collected"] += 1
        period_ids = [j.id for j in in_period]
        if period_ids:
            by_job = {j.id: j for j in in_period}
            for item in session.exec(select(ShoeRepairJobItem).where(col(ShoeRepairJobItem.shoe_repair_job_id).in_(period_ids))).all():
                if item.unit_price_cents is not None:
                    rows[by_job[item.shoe_repair_job_id].tenant_id]["billed_cents"] += int(item.unit_price_cents * item.quantity)
            for hist in session.exec(
                select(ShoeJobStatusHistory)
                .where(col(ShoeJobStatusHistory.shoe_repair_job_id).in_(period_ids), ShoeJobStatusHistory.new_status == "collected")
            ).all():
                job = by_job[hist.shoe_repair_job_id]
                turnaround[job.tenant_id].append(max((_utc(hist.created_at) - _utc(job.created_at)).total_seconds() / 86400, 0))
    for tid, days in turnaround.items():
        rows[tid]["avg_turnaround_days"] = round(sum(days) / len(days), 1)

    by_shop = sorted(rows.values(), key=lambda r: (-r["opened"], r["tenant_name"].lower()))
    all_days = [d for days in turnaround.values() for d in days]
    totals = {
        "shops": len(by_shop),
        "opened": sum(r["opened"] for r in by_shop),
        "active": sum(r["active"] for r in by_shop),
        "ready_to_collect": sum(r["ready_to_collect"] for r in by_shop),
        "collected": sum(r["collected"] for r in by_shop),
        "billed_cents": sum(r["billed_cents"] for r in by_shop),
        "avg_turnaround_days": round(sum(all_days) / len(all_days), 1) if all_days else None,
    }
    return {"from_date": start, "to_date": end, "totals": totals, "status_counts": dict(status_counts), "by_shop": by_shop}


@router.get("/me/operations/shoe-jobs/search")
def shoe_jobs_search(
    q: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=40),
    tenant_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Find a repair anywhere in the network by ticket number, customer name or phone."""
    require_hq(auth, session, "shoe")
    _, parent, _ = _parent_for_read(session, auth)
    shops = _shops(session, parent.id)
    if tenant_id is not None and tenant_id not in shops:
        raise HTTPException(status_code=404, detail="Shop not found in this network.")
    ids = [tenant_id] if tenant_id else list(shops)
    if not ids:
        return {"jobs": [], "has_more": False}
    stmt = (
        select(ShoeRepairJob, Shoe, Customer)
        .join(Shoe, Shoe.id == ShoeRepairJob.shoe_id)
        .join(Customer, Customer.id == Shoe.customer_id)
        .where(col(ShoeRepairJob.tenant_id).in_(ids))
    )
    if status:
        stmt = stmt.where(ShoeRepairJob.status == status.strip().lower())
    needle = (q or "").strip()
    if needle:
        like = f"%{needle.lower()}%"
        clauses = [col(ShoeRepairJob.job_number).ilike(like), col(Customer.full_name).ilike(like)]
        digits = normalize_phone(needle)
        if digits:
            clauses.append(Customer.phone_normalized == digits)
        from sqlalchemy import or_

        stmt = stmt.where(or_(*clauses))
    found = session.exec(stmt.order_by(col(ShoeRepairJob.created_at).desc()).limit(limit + 1)).all()
    now = datetime.now(timezone.utc)
    jobs = [
        {
            "id": str(job.id), "job_number": job.job_number, "status": job.status, "title": job.title,
            "tenant_id": str(job.tenant_id), "tenant_name": shops[job.tenant_id][0].name, "region": shops[job.tenant_id][1],
            "customer_name": customer.full_name, "shoe": " ".join(p for p in (shoe.brand, shoe.shoe_type) if p) or None,
            "created_at": job.created_at, "age_days": (now - _utc(job.created_at)).days,
        }
        for job, shoe, customer in found[:limit]
    ]
    return {"jobs": jobs, "has_more": len(found) > limit}
