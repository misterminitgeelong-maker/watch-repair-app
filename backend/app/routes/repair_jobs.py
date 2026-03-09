from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_tech_or_above
from ..models import (
    Customer,
    JobStatusHistory,
    JobStatusHistoryRead,
    RepairJob,
    RepairJobCreate,
    RepairJobRead,
    RepairJobStatusUpdate,
    Watch,
)
from .. import sms

router = APIRouter(prefix="/v1/repair-jobs", tags=["repair-jobs"])


def _next_job_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(select(func.count()).select_from(RepairJob).where(RepairJob.tenant_id == tenant_id)).one()
    return f"JOB-{int(count) + 1:05d}"


@router.post("", response_model=RepairJobRead, status_code=201)
def create_repair_job(
    payload: RepairJobCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    watch = session.get(Watch, payload.watch_id)
    if not watch or watch.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Watch not found")

    job = RepairJob(
        tenant_id=auth.tenant_id,
        job_number=_next_job_number(session, auth.tenant_id),
        **payload.model_dump(),
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
    job = session.get(RepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Repair job not found")
    return job


@router.post("/{job_id}/status", response_model=RepairJobRead)
def update_repair_job_status(
    job_id: UUID,
    payload: RepairJobStatusUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(RepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
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

    # Send status-update SMS to customer if they have a phone number
    watch = session.get(Watch, job.watch_id)
    if watch:
        customer = session.get(Customer, watch.customer_id)
        if customer and customer.phone:
            sms.notify_job_status_changed(
                session,
                tenant_id=auth.tenant_id,
                repair_job_id=job.id,
                customer_name=customer.full_name,
                to_phone=customer.phone,
                job_number=job.job_number,
                new_status=job.status,
            )

    session.commit()
    session.refresh(job)
    return job


@router.get("/{job_id}/status-history", response_model=list[JobStatusHistoryRead])
def get_repair_job_status_history(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(RepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Repair job not found")

    history = session.exec(
        select(JobStatusHistory)
        .where(JobStatusHistory.tenant_id == auth.tenant_id)
        .where(JobStatusHistory.repair_job_id == job_id)
    ).all()
    return history
