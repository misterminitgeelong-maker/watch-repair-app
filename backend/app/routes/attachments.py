import io
from pathlib import Path
from uuid import UUID, uuid4
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from PIL import Image, UnidentifiedImageError
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
    User,
    Watch,
)
from ..security import decode_access_token

router = APIRouter(prefix="/v1/attachments", tags=["attachments"])

optional_bearer = HTTPBearer(auto_error=False)

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
    raw = await file.read()
    content_type = file.content_type or "application/octet-stream"

    # Compress images on upload
    if content_type.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(raw))
            img = img.convert("RGB")
            max_dim = 2000
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85, optimize=True)
            raw = buf.getvalue()
            safe_name = Path(safe_name).stem + ".jpg"
            content_type = "image/jpeg"
        except UnidentifiedImageError:
            pass  # not a recognised image, store as-is

    storage_key = f"{uuid4().hex}_{safe_name}"
    dest = UPLOAD_DIR / storage_key
    dest.write_bytes(raw)

    attachment = Attachment(
        tenant_id=auth.tenant_id,
        repair_job_id=repair_job_id,
        watch_id=watch_id,
        uploaded_by_user_id=auth.user_id,
        storage_key=storage_key,
        file_name=safe_name,
        content_type=content_type,
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
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    access_token: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else access_token
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        subject = decode_access_token(token)
        parts = subject.split(":", maxsplit=2)
        tenant_id = UUID(parts[0])
        user_id = UUID(parts[1])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user = session.get(User, user_id)
    if not user or user.tenant_id != tenant_id or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    attachment = session.exec(
        select(Attachment)
        .where(Attachment.storage_key == storage_key)
        .where(Attachment.tenant_id == tenant_id)
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
