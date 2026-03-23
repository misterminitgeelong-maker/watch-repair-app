from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, delete, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, enforce_plan_limit, require_feature, require_tech_or_above
from ..tenant_helpers import get_tenant_repair_job
from ..models import (
    Approval,
    Attachment,
    Customer,
    SmsLogRead,
    CustomerAccount,
    CustomerAccountMembership,
    Invoice,
    JobStatusHistory,
    JobStatusHistoryRead,
    Payment,
    RepairJob,
    RepairJobCreate,
    RepairJobFieldUpdate,
    RepairJobIntakeUpdate,
    RepairJobRead,
    RepairJobStatusUpdate,
    Quote,
    QuoteLineItem,
    SmsLog,
    WorkLog,
    Watch,
)
from .. import sms

router = APIRouter(
    prefix="/v1/repair-jobs",
    tags=["repair-jobs"],
    dependencies=[Depends(require_feature("watch"))],
)


def _next_job_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(select(func.count()).select_from(RepairJob).where(RepairJob.tenant_id == tenant_id)).one()
    return f"JOB-{int(count) + 1:05d}"


@router.post("", response_model=RepairJobRead, status_code=201)
def create_repair_job(
    payload: RepairJobCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    # Plan limit check
    job_count = int(
        session.exec(select(func.count()).select_from(RepairJob).where(RepairJob.tenant_id == auth.tenant_id)).one()
    )
    enforce_plan_limit(auth, "repair_job", job_count)

    watch = session.get(Watch, payload.watch_id)
    if not watch or watch.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Watch not found")

    customer_account_id = payload.customer_account_id
    if customer_account_id:
        account = session.get(CustomerAccount, customer_account_id)
        if not account or account.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Customer account not found")
    else:
        inferred = session.exec(
            select(CustomerAccountMembership)
            .where(CustomerAccountMembership.tenant_id == auth.tenant_id)
            .where(CustomerAccountMembership.customer_id == watch.customer_id)
            .order_by(CustomerAccountMembership.created_at)
        ).first()
        customer_account_id = inferred.customer_account_id if inferred else None

    data = payload.model_dump(exclude_none=True)
    data["customer_account_id"] = customer_account_id
    job = RepairJob(
        tenant_id=auth.tenant_id,
        job_number=_next_job_number(session, auth.tenant_id),
        **data,
    )
    session.add(job)
    session.flush()

    history = JobStatusHistory(
        tenant_id=auth.tenant_id,
        repair_job_id=job.id,
        old_status=None,
        new_status=job.status,
        changed_by_user_id=auth.user_id,
        change_note="Job created",
    )
    session.add(history)

    # Send "job is live" SMS so customer can track it
    customer = session.get(Customer, watch.customer_id)
    if customer and customer.phone:
        sms.notify_job_live(
            session,
            tenant_id=auth.tenant_id,
            repair_job_id=job.id,
            customer_name=customer.full_name or "there",
            to_phone=customer.phone,
            status_token=job.status_token,
            job_number=job.job_number,
        )

    session.commit()
    session.refresh(job)
    return job


@router.get("", response_model=list[RepairJobRead])
def list_repair_jobs(
    status: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(RepairJob).where(RepairJob.tenant_id == auth.tenant_id)
    if status:
        query = query.where(RepairJob.status == status)
    return session.exec(query).all()


@router.get("/{job_id}", response_model=RepairJobRead)
def get_repair_job(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = get_tenant_repair_job(session, job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")
    return job


@router.post("/{job_id}/status", response_model=RepairJobRead)
def update_repair_job_status(
    job_id: UUID,
    payload: RepairJobStatusUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = get_tenant_repair_job(session, job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")

    previous_status = job.status
    job.status = payload.status
    session.add(job)

    history = JobStatusHistory(
        tenant_id=auth.tenant_id,
        repair_job_id=job.id,
        old_status=previous_status,
        new_status=job.status,
        changed_by_user_id=auth.user_id,
        change_note=payload.note,
    )
    session.add(history)

    # Email customer when job is ready for collection (no status SMS — we text only on job_live and quote_sent)
    watch = session.get(Watch, job.watch_id)
    if watch:
        customer = session.get(Customer, watch.customer_id)
        if customer and customer.email and job.status in ("completed", "awaiting_collection"):
            from ..email_client import send_job_ready_email
            send_job_ready_email(
                to_email=customer.email,
                customer_name=customer.full_name,
                job_number=job.job_number,
                status_token=job.status_token,
            )

    session.commit()
    session.refresh(job)
    return job


@router.post("/{job_id}/quick-status", response_model=RepairJobRead)
def quick_status_action(
    job_id: UUID,
    payload: RepairJobStatusUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    # Reuse the full status update behavior, including history and SMS.
    return update_repair_job_status(job_id=job_id, payload=payload, auth=auth, session=session)


@router.post("/{job_id}/intake", response_model=RepairJobRead)
def submit_job_intake(
    job_id: UUID,
    payload: RepairJobIntakeUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = get_tenant_repair_job(session, job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")

    checklist: list[str] = []
    if payload.has_scratches:
        checklist.append("scratches")
    if payload.has_dents:
        checklist.append("dents")
    if payload.has_cracked_crystal:
        checklist.append("cracked crystal")
    if payload.crown_missing:
        checklist.append("crown missing")
    if payload.strap_damage:
        checklist.append("strap damage")

    note_parts: list[str] = ["Ticket-in completed"]
    if checklist:
        note_parts.append(f"Condition: {', '.join(checklist)}")
    if payload.intake_notes and payload.intake_notes.strip():
        note_parts.append(payload.intake_notes.strip())
    if payload.pre_quote_cents > 0:
        note_parts.append(f"Pre-quote: ${(payload.pre_quote_cents / 100):.2f}")
    intake_note = " | ".join(note_parts)

    previous_status = job.status
    if job.status == "no_go":
        raise HTTPException(status_code=400, detail="Cannot ticket-in a cancelled/no-go job")

    if job.status == "awaiting_go_ahead":
        next_status = "go_ahead"
    else:
        next_status = job.status

    job.status = next_status
    job.pre_quote_cents = max(payload.pre_quote_cents, 0)
    if payload.intake_notes and payload.intake_notes.strip():
        existing_description = (job.description or "").strip()
        appended = f"Intake notes: {payload.intake_notes.strip()}"
        job.description = f"{existing_description}\n\n{appended}" if existing_description else appended
    session.add(job)

    session.add(
        JobStatusHistory(
            tenant_id=auth.tenant_id,
            repair_job_id=job.id,
            old_status=previous_status,
            new_status=job.status,
            changed_by_user_id=auth.user_id,
            change_note=intake_note,
        )
    )

    session.add(
        WorkLog(
            tenant_id=auth.tenant_id,
            repair_job_id=job.id,
            user_id=auth.user_id,
            note=intake_note,
            minutes_spent=0,
        )
    )

    session.commit()
    session.refresh(job)
    return job


@router.patch("/{job_id}", response_model=RepairJobRead)
def update_repair_job_fields(
    job_id: UUID,
    payload: RepairJobFieldUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = get_tenant_repair_job(session, job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")

    if payload.cost_cents is not None:
        job.cost_cents = max(0, payload.cost_cents)
    if payload.pre_quote_cents is not None:
        job.pre_quote_cents = max(0, payload.pre_quote_cents)
    if payload.priority is not None:
        job.priority = payload.priority
    if payload.salesperson is not None:
        job.salesperson = payload.salesperson
    if payload.collection_date is not None:
        job.collection_date = payload.collection_date
    if payload.deposit_cents is not None:
        job.deposit_cents = max(0, payload.deposit_cents)
    if payload.description is not None:
        job.description = payload.description
    if "customer_account_id" in payload.model_fields_set:
        if payload.customer_account_id is not None:
            account = session.get(CustomerAccount, payload.customer_account_id)
            if not account or account.tenant_id != auth.tenant_id:
                raise HTTPException(status_code=404, detail="Customer account not found")
        job.customer_account_id = payload.customer_account_id

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


@router.get("/{job_id}/sms-log", response_model=list[SmsLogRead])
def get_repair_job_sms_log(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = get_tenant_repair_job(session, job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")

    logs = session.exec(
        select(SmsLog)
        .where(SmsLog.tenant_id == auth.tenant_id)
        .where(SmsLog.repair_job_id == job_id)
        .order_by(SmsLog.created_at.desc())
    ).all()
    return [
        SmsLogRead(
            id=log.id,
            to_phone=log.to_phone,
            body=log.body,
            event=log.event,
            status=log.status,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/{job_id}/status-history", response_model=list[JobStatusHistoryRead])
def get_repair_job_status_history(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = get_tenant_repair_job(session, job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")

    history = session.exec(
        select(JobStatusHistory)
        .where(JobStatusHistory.tenant_id == auth.tenant_id)
        .where(JobStatusHistory.repair_job_id == job_id)
    ).all()
    return history


@router.delete("/{job_id}", status_code=204, response_class=Response)
def delete_repair_job(
    job_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = get_tenant_repair_job(session, job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")

    quote_ids = session.exec(
        select(Quote.id)
        .where(Quote.tenant_id == auth.tenant_id)
        .where(Quote.repair_job_id == job_id)
    ).all()
    invoice_ids = session.exec(
        select(Invoice.id)
        .where(Invoice.tenant_id == auth.tenant_id)
        .where(Invoice.repair_job_id == job_id)
    ).all()

    session.exec(
        delete(Attachment)
        .where(Attachment.tenant_id == auth.tenant_id)
        .where(Attachment.repair_job_id == job_id)
    )
    session.exec(
        delete(JobStatusHistory)
        .where(JobStatusHistory.tenant_id == auth.tenant_id)
        .where(JobStatusHistory.repair_job_id == job_id)
    )
    session.exec(
        delete(WorkLog)
        .where(WorkLog.tenant_id == auth.tenant_id)
        .where(WorkLog.repair_job_id == job_id)
    )
    session.exec(
        delete(SmsLog)
        .where(SmsLog.tenant_id == auth.tenant_id)
        .where(SmsLog.repair_job_id == job_id)
    )

    if quote_ids:
        session.exec(
            delete(Approval)
            .where(Approval.tenant_id == auth.tenant_id)
            .where(Approval.quote_id.in_(quote_ids))
        )
        session.exec(
            delete(QuoteLineItem)
            .where(QuoteLineItem.tenant_id == auth.tenant_id)
            .where(QuoteLineItem.quote_id.in_(quote_ids))
        )
        session.exec(
            delete(Quote)
            .where(Quote.tenant_id == auth.tenant_id)
            .where(Quote.id.in_(quote_ids))
        )

    if invoice_ids:
        session.exec(
            delete(Payment)
            .where(Payment.tenant_id == auth.tenant_id)
            .where(Payment.invoice_id.in_(invoice_ids))
        )
        session.exec(
            delete(Invoice)
            .where(Invoice.tenant_id == auth.tenant_id)
            .where(Invoice.id.in_(invoice_ids))
        )

    session.delete(job)
    session.commit()
    return Response(status_code=204)
