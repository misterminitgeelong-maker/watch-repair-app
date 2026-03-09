from pathlib import Path
from uuid import UUID, uuid4
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import (
    Attachment,
    AttachmentCreate,
    AttachmentRead,
    AttachmentUrlResponse,
    RepairJob,
    Watch,
)

router = APIRouter(prefix="/v1/attachments", tags=["attachments"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("", response_model=AttachmentRead, status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    repair_job_id: UUID | None = None,
    watch_id: UUID | None = None,
    label: str | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    if not repair_job_id and not watch_id:
        raise HTTPException(status_code=400, detail="repair_job_id or watch_id is required")

    if repair_job_id:
        job = session.get(RepairJob, repair_job_id)
        if not job or job.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Repair job not found")

    if watch_id:
        watch = session.get(Watch, watch_id)
        if not watch or watch.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Watch not found")

    safe_name = Path(file.filename or "file").name
    storage_key = f"{uuid4().hex}_{safe_name}"
    dest = UPLOAD_DIR / storage_key
    dest.write_bytes(await file.read())

    attachment = Attachment(
        tenant_id=auth.tenant_id,
        repair_job_id=repair_job_id,
        watch_id=watch_id,
        uploaded_by_user_id=auth.user_id,
        storage_key=storage_key,
        file_name=safe_name,
        content_type=file.content_type or "application/octet-stream",
        file_size_bytes=dest.stat().st_size,
        label=label,
    )
    session.add(attachment)
    session.commit()
    session.refresh(attachment)
    return AttachmentRead(**attachment.model_dump())


@router.get("/download/{storage_key:path}")
def download_attachment(
    storage_key: str,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    attachment = session.exec(
        select(Attachment)
        .where(Attachment.storage_key == storage_key)
        .where(Attachment.tenant_id == auth.tenant_id)
    ).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Not found")
    dest = UPLOAD_DIR / storage_key
    if not dest.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(dest), filename=attachment.file_name or storage_key, media_type=attachment.content_type or "application/octet-stream")


@router.get("", response_model=list[AttachmentRead])
def list_attachments(
    repair_job_id: UUID | None = None,
    watch_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(Attachment).where(Attachment.tenant_id == auth.tenant_id)
    if repair_job_id:
        query = query.where(Attachment.repair_job_id == repair_job_id)
    if watch_id:
        query = query.where(Attachment.watch_id == watch_id)

    rows = session.exec(query).all()
    return [AttachmentRead(**row.model_dump()) for row in rows]
