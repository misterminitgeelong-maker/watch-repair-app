from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import WorkLog, WorkLogCreate, WorkLogRead
from ..tenant_helpers import get_tenant_repair_job

router = APIRouter(prefix="/v1/work-logs", tags=["work-logs"])


@router.post("", response_model=WorkLogRead, status_code=201)
def create_work_log(
    payload: WorkLogCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = get_tenant_repair_job(session, payload.repair_job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")

    work_log = WorkLog(
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        **payload.model_dump(),
    )
    session.add(work_log)
    session.commit()
    session.refresh(work_log)
    return WorkLogRead(**work_log.model_dump())


@router.get("", response_model=list[WorkLogRead])
def list_work_logs(
    repair_job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = get_tenant_repair_job(session, repair_job_id, auth.tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repair job not found")

    logs = session.exec(
        select(WorkLog)
        .where(WorkLog.tenant_id == auth.tenant_id)
        .where(WorkLog.repair_job_id == repair_job_id)
    ).all()
    return [WorkLogRead(**log.model_dump()) for log in logs]
