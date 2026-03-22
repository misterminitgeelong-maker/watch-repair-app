from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, delete, func, select

from ..database import get_session
from ..dependencies import AuthContext, enforce_plan_limit, get_auth_context, require_feature, require_tech_or_above
from ..models import (
    Attachment,
    CustomService,
    Customer,
    CustomerAccount,
    CustomerAccountMembership,
    Shoe,
    ShoeCreate,
    ShoeRead,
    ShoeRepairJob,
    ShoeRepairJobCreate,
    ShoeRepairJobFieldUpdate,
    ShoeRepairJobItem,
    ShoeRepairJobItemCreate,
    ShoeRepairJobItemRead,
    ShoeRepairJobItemsAppend,
    ShoeRepairJobRead,
    ShoeRepairJobShoe,
    ShoeRepairJobShoeRead,
    ShoeRepairJobStatusUpdate,
)

router = APIRouter(
    prefix="/v1/shoe-repair-jobs",
    tags=["shoe-repair-jobs"],
    dependencies=[Depends(require_feature("shoe"))],
)


def _next_shoe_job_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(
        select(func.count()).select_from(ShoeRepairJob).where(ShoeRepairJob.tenant_id == tenant_id)
    ).one()
    return f"SHO-{int(count) + 1:05d}"


def _load_items(session: Session, job_id: UUID) -> list[ShoeRepairJobItemRead]:
    rows = session.exec(
        select(ShoeRepairJobItem).where(ShoeRepairJobItem.shoe_repair_job_id == job_id)
    ).all()
    return [ShoeRepairJobItemRead.model_validate(r) for r in rows]


def _create_job_items(
    session: Session,
    *,
    tenant_id: UUID,
    job_id: UUID,
    items: list[ShoeRepairJobItemCreate],
) -> None:
    for item in items:
        session.add(
            ShoeRepairJobItem(
                tenant_id=tenant_id,
                shoe_repair_job_id=job_id,
                **item.model_dump(),
            )
        )


# Jobs considered "in queue" for FIFO estimated completion
_ACTIVE_QUEUE_STATUSES = frozenset({
    "awaiting_quote", "awaiting_go_ahead", "go_ahead", "working_on", "awaiting_parts",
})


def _get_catalogue_item(session: Session, tenant_id: UUID, catalogue_key: str) -> dict | None:
    """Resolve catalogue item from built-in or custom services."""
    if catalogue_key.startswith("custom__"):
        try:
            sid = UUID(catalogue_key.replace("custom__", "", 1))
            cs = session.get(CustomService, sid)
            if cs and cs.tenant_id == tenant_id and cs.service_type == "shoe":
                return {
                    "estimated_days_min": 3,
                    "estimated_days_max": 7,
                    "complexity": "standard",
                }
        except (ValueError, TypeError):
            pass
        return None
    from .shoe_catalogue import _ITEM_INDEX
    return _ITEM_INDEX.get(catalogue_key)


def _get_job_estimated_days(session: Session, job: ShoeRepairJob) -> int:
    """Return estimated_days_max for a job from its catalogue items. Default 5 if unknown."""
    items = session.exec(
        select(ShoeRepairJobItem).where(ShoeRepairJobItem.shoe_repair_job_id == job.id)
    ).all()
    days = 0
    for item in items:
        cat = _get_catalogue_item(session, job.tenant_id, item.catalogue_key)
        if cat:
            dmax = cat.get("estimated_days_max", 7)
            days = max(days, dmax)
    return days if days else 5


def _compute_queue_estimated_ready_by(session: Session, tenant_id: UUID) -> dict[UUID, date]:
    """FIFO queue: for each active job, compute estimated_ready_by from work ahead + own days."""
    jobs = session.exec(
        select(ShoeRepairJob)
        .where(ShoeRepairJob.tenant_id == tenant_id)
        .where(ShoeRepairJob.status.in_(_ACTIVE_QUEUE_STATUSES))
        .order_by(ShoeRepairJob.created_at.asc())
    ).all()
    result: dict = {}
    cumulative_days = 0
    for job in jobs:
        job_days = _get_job_estimated_days(session, job)
        work_ahead = cumulative_days
        total_days = work_ahead + job_days
        ready = job.created_at + timedelta(days=int(total_days))
        result[job.id] = ready.date()
        cumulative_days += job_days
    return result


def _job_to_read(job: ShoeRepairJob, session: Session, queue_ready: dict | None = None) -> ShoeRepairJobRead:
    data = job.model_dump()
    items = _load_items(session, job.id)
    data["items"] = items

    # Compute complexity and estimated turnaround from catalogue (built-in or custom)
    complexity_order = {"simple": 0, "standard": 1, "complex": 2}
    days_min, days_max = 0, 0
    max_comp = "simple"
    for item in items:
        cat = _get_catalogue_item(session, job.tenant_id, item.catalogue_key)
        if cat:
            comp = cat.get("complexity", "standard")
            max_comp = max(max_comp, comp, key=lambda c: complexity_order.get(c, 0))
            dmin, dmax = cat.get("estimated_days_min", 3), cat.get("estimated_days_max", 7)
            days_min = max(days_min, dmin)
            days_max = max(days_max, dmax)
    if items:
        data["complexity"] = max_comp
        data["estimated_days_min"] = days_min or 3
        data["estimated_days_max"] = days_max or 7
    if queue_ready is not None and job.id in queue_ready:
        data["estimated_ready_by"] = queue_ready[job.id]
    # Primary shoe details
    primary_shoe = session.get(Shoe, job.shoe_id)
    data["shoe"] = ShoeRead.model_validate(primary_shoe) if primary_shoe else None
    # Extra shoes
    extra_rows = session.exec(
        select(ShoeRepairJobShoe)
        .where(ShoeRepairJobShoe.shoe_repair_job_id == job.id)
        .order_by(ShoeRepairJobShoe.sort_order)
    ).all()
    extra = []
    for ej in extra_rows:
        sh = session.get(Shoe, ej.shoe_id)
        extra.append(ShoeRepairJobShoeRead(
            id=ej.id,
            shoe_id=ej.shoe_id,
            shoe=ShoeRead.model_validate(sh) if sh else None,
            sort_order=ej.sort_order,
        ))
    data["extra_shoes"] = extra
    return ShoeRepairJobRead(**data)


# ── Shoes (item being repaired) ───────────────────────────────────────────────

@router.post("/shoes", response_model=ShoeRead, status_code=201)
def create_shoe(
    payload: ShoeCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    customer = session.get(Customer, payload.customer_id)
    if not customer or customer.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    shoe = Shoe(tenant_id=auth.tenant_id, **payload.model_dump())
    session.add(shoe)
    session.commit()
    session.refresh(shoe)
    return shoe


@router.get("/shoes", response_model=list[ShoeRead])
def list_shoes(
    customer_id: UUID | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(Shoe).where(Shoe.tenant_id == auth.tenant_id)
    if customer_id:
        query = query.where(Shoe.customer_id == customer_id)
    return session.exec(query).all()


# ── Shoe Repair Jobs ──────────────────────────────────────────────────────────

@router.post("", response_model=ShoeRepairJobRead, status_code=201)
def create_shoe_repair_job(
    payload: ShoeRepairJobCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    # Plan limit check
    shoe_job_count = int(
        session.exec(
            select(func.count()).select_from(ShoeRepairJob).where(ShoeRepairJob.tenant_id == auth.tenant_id)
        ).one()
    )
    enforce_plan_limit(auth, "shoe_job", shoe_job_count)

    shoe = session.get(Shoe, payload.shoe_id)
    if not shoe or shoe.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe not found")

    customer_account_id = payload.customer_account_id
    if customer_account_id:
        account = session.get(CustomerAccount, customer_account_id)
        if not account or account.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Customer account not found")
    else:
        inferred = session.exec(
            select(CustomerAccountMembership)
            .where(CustomerAccountMembership.tenant_id == auth.tenant_id)
            .where(CustomerAccountMembership.customer_id == shoe.customer_id)
            .order_by(CustomerAccountMembership.created_at)
        ).first()
        customer_account_id = inferred.customer_account_id if inferred else None

    items_data = payload.items
    job_data = payload.model_dump(exclude={"items"})
    job_data["customer_account_id"] = customer_account_id

    job = ShoeRepairJob(
        tenant_id=auth.tenant_id,
        job_number=_next_shoe_job_number(session, auth.tenant_id),
        **job_data,
    )
    session.add(job)
    session.flush()

    _create_job_items(session, tenant_id=auth.tenant_id, job_id=job.id, items=items_data)

    session.commit()
    session.refresh(job)
    return _job_to_read(job, session)


@router.get("", response_model=list[ShoeRepairJobRead])
def list_shoe_repair_jobs(
    status: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(ShoeRepairJob).where(ShoeRepairJob.tenant_id == auth.tenant_id)
    if status:
        query = query.where(ShoeRepairJob.status == status)
    jobs = session.exec(query.order_by(ShoeRepairJob.created_at.desc())).all()
    queue_ready = _compute_queue_estimated_ready_by(session, auth.tenant_id)
    return [_job_to_read(j, session, queue_ready) for j in jobs]


@router.get("/{job_id}", response_model=ShoeRepairJobRead)
def get_shoe_repair_job(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    queue_ready = _compute_queue_estimated_ready_by(session, auth.tenant_id)
    return _job_to_read(job, session, queue_ready)


@router.post("/{job_id}/status", response_model=ShoeRepairJobRead)
def update_shoe_repair_job_status(
    job_id: UUID,
    payload: ShoeRepairJobStatusUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    job.status = payload.status
    session.add(job)
    session.commit()
    session.refresh(job)
    return _job_to_read(job, session)


@router.patch("/{job_id}", response_model=ShoeRepairJobRead)
def update_shoe_repair_job(
    job_id: UUID,
    payload: ShoeRepairJobFieldUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    update_data = payload.model_dump(exclude_unset=True)
    if "customer_account_id" in update_data and update_data["customer_account_id"] is not None:
        account = session.get(CustomerAccount, update_data["customer_account_id"])
        if not account or account.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Customer account not found")
    for field, value in update_data.items():
        setattr(job, field, value)
    session.add(job)
    session.commit()
    session.refresh(job)
    return _job_to_read(job, session)


@router.post("/{job_id}/items", response_model=ShoeRepairJobRead, status_code=201)
def append_shoe_repair_job_items(
    job_id: UUID,
    payload: ShoeRepairJobItemsAppend,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    if payload.items:
        _create_job_items(session, tenant_id=auth.tenant_id, job_id=job.id, items=payload.items)
        session.commit()
        session.refresh(job)
    return _job_to_read(job, session)


# ── Extra shoes on a job ──────────────────────────────────────────────────────

from pydantic import BaseModel as _BM


class _AddShoeBody(_BM):
    shoe_id: str


@router.post("/{job_id}/shoes", response_model=ShoeRepairJobRead, status_code=201)
def add_shoe_to_job(
    job_id: UUID,
    payload: _AddShoeBody,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    shoe = session.get(Shoe, UUID(payload.shoe_id))
    if not shoe or shoe.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe not found")
    # Determine next sort_order
    existing = session.exec(
        select(ShoeRepairJobShoe).where(ShoeRepairJobShoe.shoe_repair_job_id == job_id)
    ).all()
    sort_order = len(existing) + 1
    entry = ShoeRepairJobShoe(
        tenant_id=auth.tenant_id,
        shoe_repair_job_id=job_id,
        shoe_id=shoe.id,
        sort_order=sort_order,
    )
    session.add(entry)
    session.commit()
    return _job_to_read(job, session)


@router.delete("/{job_id}/shoes/{entry_id}", response_model=ShoeRepairJobRead)
def remove_shoe_from_job(
    job_id: UUID,
    entry_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    entry = session.get(ShoeRepairJobShoe, entry_id)
    if not entry or entry.shoe_repair_job_id != job_id:
        raise HTTPException(status_code=404, detail="Shoe entry not found")
    session.delete(entry)
    session.commit()
    return _job_to_read(job, session)


@router.delete("/{job_id}", status_code=204, response_class=Response)
def delete_shoe_repair_job(
    job_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")

    session.exec(
        delete(Attachment)
        .where(Attachment.tenant_id == auth.tenant_id)
        .where(Attachment.shoe_repair_job_id == job_id)
    )
    session.exec(
        delete(ShoeRepairJobItem)
        .where(ShoeRepairJobItem.tenant_id == auth.tenant_id)
        .where(ShoeRepairJobItem.shoe_repair_job_id == job_id)
    )
    session.exec(
        delete(ShoeRepairJobShoe)
        .where(ShoeRepairJobShoe.tenant_id == auth.tenant_id)
        .where(ShoeRepairJobShoe.shoe_repair_job_id == job_id)
    )

    session.delete(job)
    session.commit()
    return Response(status_code=204)
