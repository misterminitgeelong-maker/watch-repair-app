from datetime import timedelta, timezone, datetime
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
    ShoeJobStatusHistory,
    JobNotePayload,
    ShoeJobStatusHistoryRead,
    SmsLog,
    SmsLogRead,
    TenantEventLog,
)
from .. import sms as sms_service
from ..config import settings

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
    # Resolve claimed_by_name
    if job.claimed_by_user_id:
        from ..models import User as UserModel
        u = session.get(UserModel, job.claimed_by_user_id)
        data["claimed_by_name"] = u.full_name if u else None
    else:
        data["claimed_by_name"] = None
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

    # Record initial status history
    session.add(ShoeJobStatusHistory(
        tenant_id=auth.tenant_id,
        shoe_repair_job_id=job.id,
        old_status=None,
        new_status=job.status,
        changed_by_user_id=auth.user_id,
        change_note="Job created",
    ))

    session.commit()
    session.refresh(job)

    # Send "job live" SMS if customer has a phone
    customer = session.get(Customer, shoe.customer_id)
    if customer and customer.phone:
        sms_service.notify_shoe_job_live(
            session,
            tenant_id=auth.tenant_id,
            shoe_repair_job_id=job.id,
            customer_name=customer.first_name or customer.name or "there",
            to_phone=customer.phone,
            status_token=job.status_token,
            job_number=job.job_number,
        )
        session.commit()

    return _job_to_read(job, session)


@router.get("", response_model=list[ShoeRepairJobRead])
def list_shoe_repair_jobs(
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),
    cost_outlier: bool | None = Query(default=None, description="When true, only include jobs with outlier cost values"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(ShoeRepairJob).where(ShoeRepairJob.tenant_id == auth.tenant_id)
    if status:
        query = query.where(ShoeRepairJob.status == status)
    if customer_id:
        shoe_ids = select(Shoe.id).where(Shoe.tenant_id == auth.tenant_id).where(Shoe.customer_id == customer_id)
        query = query.where(ShoeRepairJob.shoe_id.in_(shoe_ids))
    if cost_outlier:
        query = query.where(ShoeRepairJob.cost_cents > 5_000_000)
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
    old_status = job.status
    job.status = payload.status
    session.add(job)

    # Record history
    session.add(ShoeJobStatusHistory(
        tenant_id=auth.tenant_id,
        shoe_repair_job_id=job.id,
        old_status=old_status,
        new_status=payload.status,
        changed_by_user_id=auth.user_id,
        change_note=payload.note,
    ))

    session.commit()
    session.refresh(job)

    # SMS notification on milestone statuses
    shoe = session.get(Shoe, job.shoe_id)
    customer = session.get(Customer, shoe.customer_id) if shoe else None
    if customer and customer.phone:
        sms_service.notify_shoe_job_status_changed(
            session,
            tenant_id=auth.tenant_id,
            shoe_repair_job_id=job.id,
            customer_name=customer.first_name or customer.name or "there",
            to_phone=customer.phone,
            job_number=job.job_number,
            status_token=job.status_token,
            new_status=payload.status,
        )
        session.commit()

    return _job_to_read(job, session)


@router.post("/{job_id}/note", status_code=204, response_class=Response)
def add_shoe_repair_job_note(
    job_id: UUID,
    payload: JobNotePayload,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Add a free-text note to the shoe job history without changing its status."""
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    if not payload.note.strip():
        raise HTTPException(status_code=422, detail="note must not be empty")
    history = ShoeJobStatusHistory(
        tenant_id=auth.tenant_id,
        shoe_repair_job_id=job.id,
        old_status=job.status,
        new_status=job.status,
        changed_by_user_id=auth.user_id,
        change_note=payload.note.strip(),
    )
    session.add(history)
    session.commit()
    return Response(status_code=204)


@router.get("/{job_id}/status-history", response_model=list[ShoeJobStatusHistoryRead])
def get_shoe_repair_job_status_history(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    return session.exec(
        select(ShoeJobStatusHistory)
        .where(ShoeJobStatusHistory.tenant_id == auth.tenant_id)
        .where(ShoeJobStatusHistory.shoe_repair_job_id == job_id)
        .order_by(ShoeJobStatusHistory.created_at.desc())
    ).all()


@router.post("/{job_id}/claim", response_model=ShoeRepairJobRead)
def claim_shoe_repair_job(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Mark this shoe job as claimed by the current user."""
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    job.claimed_by_user_id = auth.user_id
    session.add(job)
    session.commit()
    session.refresh(job)
    return _job_to_read(job, session)


@router.post("/{job_id}/release", response_model=ShoeRepairJobRead)
def release_shoe_repair_job(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Release a claim on this shoe job."""
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    job.claimed_by_user_id = None
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


@router.delete("/{job_id}/items/{item_id}", response_model=ShoeRepairJobRead)
def remove_shoe_repair_job_item(
    job_id: UUID,
    item_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    item = session.get(ShoeRepairJobItem, item_id)
    if not item or item.shoe_repair_job_id != job_id:
        raise HTTPException(status_code=404, detail="Item not found")
    session.delete(item)
    session.commit()
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


# ── Quote approval ──────────────────────────────────────────────────────────

QUOTE_TTL_HOURS = getattr(settings, "quote_approval_token_ttl_hours", 168)


@router.post("/{job_id}/send-quote", response_model=ShoeRepairJobRead)
def send_shoe_quote(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Send a quote approval SMS to the customer with approve/decline link."""
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")

    # Calculate total from items
    items = session.exec(
        select(ShoeRepairJobItem).where(ShoeRepairJobItem.shoe_repair_job_id == job.id)
    ).all()
    total_cents = int(sum((i.unit_price_cents or 0) * i.quantity for i in items if i.unit_price_cents is not None))

    # Set expiry and mark quote as sent
    job.quote_approval_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=QUOTE_TTL_HOURS)
    job.quote_status = "sent"
    session.add(job)

    # Log the event
    session.add(TenantEventLog(
        tenant_id=auth.tenant_id,
        entity_type="shoe_repair_job",
        entity_id=job.id,
        event_type="shoe_quote_sent",
        event_summary=f"Quote sent for shoe job #{job.job_number} (${total_cents / 100:.2f})",
        actor_user_id=auth.user_id,
    ))

    session.commit()
    session.refresh(job)

    # Send SMS if customer has phone
    shoe = session.get(Shoe, job.shoe_id)
    customer = session.get(Customer, shoe.customer_id) if shoe else None
    if customer and customer.phone:
        # Get tenant name for shop name
        from ..models import Tenant
        tenant = session.get(Tenant, auth.tenant_id)
        shop_name = (tenant.name if tenant else None) or "your shoe repair shop"
        sms_service.notify_shoe_quote_sent(
            session,
            tenant_id=auth.tenant_id,
            shoe_repair_job_id=job.id,
            customer_name=customer.first_name or customer.name or "there",
            to_phone=customer.phone,
            total_cents=total_cents,
            approval_token=job.quote_approval_token,
            shop_name=shop_name,
        )
        session.commit()
    elif not (customer and customer.phone):
        raise HTTPException(status_code=422, detail="Customer has no phone number. Update the customer record first.")

    return _job_to_read(job, session)


# ── SMS log & resend ──────────────────────────────────────────────────────────

@router.get("/{job_id}/sms-log", response_model=list[SmsLogRead])
def get_shoe_job_sms_log(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    logs = session.exec(
        select(SmsLog)
        .where(SmsLog.tenant_id == auth.tenant_id)
        .where(SmsLog.shoe_repair_job_id == job_id)
        .order_by(SmsLog.created_at.asc())
    ).all()
    return logs


class _ResendPayload(_BM):
    event: str


@router.post("/{job_id}/resend-notification", response_model=SmsLogRead, status_code=201)
def resend_shoe_notification(
    job_id: UUID,
    payload: _ResendPayload,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Shoe repair job not found")
    shoe = session.get(Shoe, job.shoe_id)
    customer = session.get(Customer, shoe.customer_id) if shoe else None
    if not customer or not customer.phone:
        raise HTTPException(status_code=422, detail="No phone number on customer record")

    event = payload.event
    customer_name = customer.first_name or customer.name or "there"

    if event == "job_live":
        sms_service.notify_shoe_job_live(
            session,
            tenant_id=auth.tenant_id,
            shoe_repair_job_id=job.id,
            customer_name=customer_name,
            to_phone=customer.phone,
            status_token=job.status_token,
            job_number=job.job_number,
        )
    elif event.startswith("status_"):
        status_slug = event[len("status_"):]
        sms_service.notify_shoe_job_status_changed(
            session,
            tenant_id=auth.tenant_id,
            shoe_repair_job_id=job.id,
            customer_name=customer_name,
            to_phone=customer.phone,
            job_number=job.job_number,
            status_token=job.status_token,
            new_status=status_slug,
        )
    else:
        raise HTTPException(status_code=422, detail=f"Unknown event: {event}")

    session.commit()
    # Return the most recent log entry for this job
    log = session.exec(
        select(SmsLog)
        .where(SmsLog.shoe_repair_job_id == job.id)
        .order_by(SmsLog.created_at.desc())
    ).first()
    return log
