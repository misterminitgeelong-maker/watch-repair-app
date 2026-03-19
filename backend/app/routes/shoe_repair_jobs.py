from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, delete, func, select

from ..database import get_session
from ..dependencies import AuthContext, enforce_plan_limit, get_auth_context, require_feature, require_tech_or_above
from ..models import (
    Attachment,
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


def _job_to_read(job: ShoeRepairJob, session: Session) -> ShoeRepairJobRead:
    data = job.model_dump()
    data["items"] = _load_items(session, job.id)
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
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(ShoeRepairJob).where(ShoeRepairJob.tenant_id == auth.tenant_id)
    if status:
        query = query.where(ShoeRepairJob.status == status)
    jobs = session.exec(query.order_by(ShoeRepairJob.created_at.desc()).offset(skip).limit(limit)).all()
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
