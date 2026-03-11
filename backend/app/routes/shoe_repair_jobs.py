from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import (
    Customer,
    Shoe,
    ShoeCreate,
    ShoeRead,
    ShoeRepairJob,
    ShoeRepairJobCreate,
    ShoeRepairJobFieldUpdate,
    ShoeRepairJobItem,
    ShoeRepairJobItemRead,
    ShoeRepairJobRead,
    ShoeRepairJobStatusUpdate,
)

router = APIRouter(prefix="/v1/shoe-repair-jobs", tags=["shoe-repair-jobs"])


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


def _job_to_read(job: ShoeRepairJob, session: Session) -> ShoeRepairJobRead:
    data = job.model_dump()
    data["items"] = _load_items(session, job.id)
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
    shoe = session.get(Shoe, payload.shoe_id)
    if not shoe or shoe.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe not found")

    items_data = payload.items
    job_data = payload.model_dump(exclude={"items"})

    job = ShoeRepairJob(
        tenant_id=auth.tenant_id,
        job_number=_next_shoe_job_number(session, auth.tenant_id),
        **job_data,
    )
    session.add(job)
    session.flush()

    for item in items_data:
        session.add(
            ShoeRepairJobItem(
                tenant_id=auth.tenant_id,
                shoe_repair_job_id=job.id,
                **item.model_dump(),
            )
        )

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
    return [_job_to_read(j, session) for j in jobs]


@router.get("/{job_id}", response_model=ShoeRepairJobRead)
def get_shoe_repair_job(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    return _job_to_read(job, session)


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
    for field, value in update_data.items():
        setattr(job, field, value)
    session.add(job)
    session.commit()
    session.refresh(job)
    return _job_to_read(job, session)
