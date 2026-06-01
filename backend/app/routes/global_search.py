"""Unified Cmd+K search across job types and customers."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import AutoKeyJob, Customer, Invoice, RepairJob, ShoeRepairJob

router = APIRouter(prefix="/v1", tags=["search"])


class GlobalSearchHit(BaseModel):
    kind: str  # repair_job | shoe_repair_job | auto_key_job | customer | quote | invoice
    id: UUID
    title: str
    subtitle: str | None = None
    status: str | None = None
    href: str


class GlobalSearchResponse(BaseModel):
    hits: list[GlobalSearchHit]


def _pattern(q: str) -> str:
    return f"%{q.lower().strip()}%"


@router.get("/search", response_model=GlobalSearchResponse)
def global_search(
    q: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(default=8, ge=1, le=20),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    pattern = _pattern(q)
    per_type = max(2, limit // 3)
    hits: list[GlobalSearchHit] = []
    tid = auth.tenant_id

    for j in session.exec(
        select(RepairJob)
        .where(RepairJob.tenant_id == tid)
        .where(
            func.lower(RepairJob.title).like(pattern)
            | func.lower(RepairJob.job_number).like(pattern)
        )
        .order_by(RepairJob.created_at.desc())
        .limit(per_type)
    ).all():
        hits.append(
            GlobalSearchHit(
                kind="repair_job",
                id=j.id,
                title=j.title or j.job_number,
                subtitle=j.job_number,
                status=j.status,
                href=f"/jobs/{j.id}",
            )
        )

    for j in session.exec(
        select(ShoeRepairJob)
        .where(ShoeRepairJob.tenant_id == tid)
        .where(
            func.lower(ShoeRepairJob.job_number).like(pattern)
            | func.lower(ShoeRepairJob.title).like(pattern)
            | func.lower(ShoeRepairJob.description).like(pattern)
        )
        .order_by(ShoeRepairJob.created_at.desc())
        .limit(per_type)
    ).all():
        hits.append(
            GlobalSearchHit(
                kind="shoe_repair_job",
                id=j.id,
                title=f"Shoe #{j.job_number}",
                subtitle=j.status,
                status=j.status,
                href=f"/shoe-repairs/{j.id}",
            )
        )

    for j in session.exec(
        select(AutoKeyJob)
        .where(AutoKeyJob.tenant_id == tid)
        .where(
            func.lower(AutoKeyJob.job_number).like(pattern)
            | func.lower(AutoKeyJob.title).like(pattern)
            | func.lower(AutoKeyJob.vehicle_make).like(pattern)
            | func.lower(AutoKeyJob.vehicle_model).like(pattern)
        )
        .order_by(AutoKeyJob.created_at.desc())
        .limit(per_type)
    ).all():
        hits.append(
            GlobalSearchHit(
                kind="auto_key_job",
                id=j.id,
                title=j.title or j.job_number,
                subtitle=j.job_number,
                status=j.status,
                href=f"/auto-key/{j.id}",
            )
        )

    for c in session.exec(
        select(Customer)
        .where(Customer.tenant_id == tid)
        .where(
            func.lower(Customer.full_name).like(pattern)
            | func.lower(Customer.email).like(pattern)
            | func.lower(Customer.phone).like(pattern)
        )
        .order_by(Customer.full_name.asc())
        .limit(per_type)
    ).all():
        hits.append(
            GlobalSearchHit(
                kind="customer",
                id=c.id,
                title=c.full_name or "Customer",
                subtitle=" · ".join(x for x in [c.phone, c.email] if x) or None,
                href=f"/customers/{c.id}",
            )
        )

    for inv in session.exec(
        select(Invoice)
        .where(Invoice.tenant_id == tid)
        .where(func.lower(Invoice.invoice_number).like(pattern))
        .order_by(Invoice.created_at.desc())
        .limit(3)
    ).all():
        hits.append(
            GlobalSearchHit(
                kind="invoice",
                id=inv.id,
                title=f"Invoice {inv.invoice_number}",
                subtitle=inv.status,
                status=inv.status,
                href=f"/invoices/{inv.id}",
            )
        )

    return GlobalSearchResponse(hits=hits[:limit])
