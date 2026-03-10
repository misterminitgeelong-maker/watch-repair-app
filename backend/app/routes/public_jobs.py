import io
import importlib

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import JobStatusHistory, RepairJob, Watch

router = APIRouter(prefix="/v1/public", tags=["public-jobs"])


@router.get("/jobs/{status_token}")
def get_public_job_status(status_token: str, session: Session = Depends(get_session)):
    job = session.exec(select(RepairJob).where(RepairJob.status_token == status_token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    watch = session.get(Watch, job.watch_id)
    history = session.exec(
        select(JobStatusHistory)
        .where(JobStatusHistory.repair_job_id == job.id)
        .order_by(JobStatusHistory.created_at)
    ).all()

    return {
        "job_number": job.job_number,
        "status": job.status,
        "title": job.title,
        "description": job.description,
        "priority": job.priority,
        "pre_quote_cents": job.pre_quote_cents,
        "created_at": job.created_at,
        "watch": {
            "brand": watch.brand if watch else None,
            "model": watch.model if watch else None,
            "serial_number": watch.serial_number if watch else None,
        },
        "history": [
            {
                "old_status": entry.old_status,
                "new_status": entry.new_status,
                "change_note": entry.change_note,
                "created_at": entry.created_at,
            }
            for entry in history
        ],
    }


@router.get("/jobs/{status_token}/qr")
def get_public_job_qr(status_token: str, session: Session = Depends(get_session)):
    job = session.exec(select(RepairJob).where(RepairJob.status_token == status_token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    target_url = f"{settings.public_base_url}/status/{status_token}"
    qrcode = importlib.import_module("qrcode")
    image = qrcode.make(target_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")
