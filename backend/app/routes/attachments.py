import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from PIL import Image, UnidentifiedImageError
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import (
    Attachment,
    AttachmentCreate,
    AttachmentRead,
    AttachmentUrlResponse,
    AutoKeyJob,
    RepairJob,
    ShoeRepairJob,
    User,
    Watch,
)
from ..security import decode_access_token
from ..services.attachment_storage import (
    AttachmentNotFoundError,
    InvalidStorageKeyError,
    LocalAttachmentStorage,
)

router = APIRouter(prefix="/v1/attachments", tags=["attachments"])

optional_bearer = HTTPBearer(auto_error=False)
SIGNED_DOWNLOAD_TOKEN_TYP = "attachment_download"
SIGNED_DOWNLOAD_EXPIRE_SECONDS = 300

attachment_storage = LocalAttachmentStorage(settings.attachment_local_upload_dir)


def _allowed_content_types() -> set[str]:
    return {ct.strip().lower() for ct in settings.attachment_allowed_content_types.split(",") if ct.strip()}


def _attachment_signing_secret() -> str:
    """Return the secret used to sign short-lived download URLs.

    Prefer a dedicated ATTACHMENT_SIGNING_SECRET so a leaked download URL does
    not share signing material with auth tokens. Falls back to JWT_SECRET for
    backward compatibility. Access tokens already reject typ=attachment_download
    (see security._parse_claims), so collision risk is low either way.
    """
    secret = (settings.attachment_signing_secret or "").strip()
    return secret if secret else settings.jwt_secret


def _create_signed_download_token(*, tenant_id: UUID, user_id: UUID, storage_key: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(seconds=SIGNED_DOWNLOAD_EXPIRE_SECONDS)
    payload = {
        "sub": f"{tenant_id}:{user_id}",
        "typ": SIGNED_DOWNLOAD_TOKEN_TYP,
        "purpose": "download",
        "sk": storage_key,
        "exp": expire,
    }
    return jwt.encode(payload, _attachment_signing_secret(), algorithm=settings.jwt_algorithm)


def _decode_signed_download_token(token: str) -> tuple[UUID, UUID, str]:
    try:
        payload = jwt.decode(
            token, _attachment_signing_secret(), algorithms=[settings.jwt_algorithm]
        )
        if payload.get("typ") != SIGNED_DOWNLOAD_TOKEN_TYP:
            raise ValueError("Invalid token type")
        if payload.get("purpose") not in (None, "download"):
            raise ValueError("Invalid token purpose")
        subject = payload.get("sub")
        storage_key = payload.get("sk")
        if not isinstance(subject, str) or not isinstance(storage_key, str):
            raise ValueError("Invalid token payload")
        tenant_raw, user_raw = subject.split(":", maxsplit=1)
        return UUID(tenant_raw), UUID(user_raw), storage_key
    except (JWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid download token") from exc


@router.post("", response_model=AttachmentRead, status_code=201)
async def upload_attachment(
    file: UploadFile = File(...),
    repair_job_id: UUID | None = None,
    watch_id: UUID | None = None,
    shoe_repair_job_id: UUID | None = None,
    auto_key_job_id: UUID | None = None,
    label: str | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    if not repair_job_id and not watch_id and not shoe_repair_job_id and not auto_key_job_id:
        raise HTTPException(status_code=400, detail="repair_job_id, watch_id, shoe_repair_job_id, or auto_key_job_id is required")

    if repair_job_id:
        job = session.get(RepairJob, repair_job_id)
        if not job or job.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Repair job not found")

    if watch_id:
        watch = session.get(Watch, watch_id)
        if not watch or watch.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Watch not found")

    if shoe_repair_job_id:
        shoe_job = session.get(ShoeRepairJob, shoe_repair_job_id)
        if not shoe_job or shoe_job.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Shoe repair job not found")

    if auto_key_job_id:
        ak_job = session.get(AutoKeyJob, auto_key_job_id)
        if not ak_job or ak_job.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Auto key job not found")

    safe_name = Path(file.filename or "file").name
    raw = await file.read()
    content_type = (file.content_type or "application/octet-stream").lower()

    if content_type not in _allowed_content_types():
        raise HTTPException(status_code=415, detail="Unsupported file type")
    if len(raw) > settings.attachment_max_upload_bytes:
        raise HTTPException(status_code=413, detail="File too large")

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

    file_id = uuid4().hex
    if auto_key_job_id:
        job_subdir = f"auto-key-photos/{auto_key_job_id}"
        storage_key = f"{job_subdir}/{file_id}_{safe_name}"
    else:
        storage_key = f"{file_id}_{safe_name}"
    file_size = attachment_storage.save_bytes(storage_key, raw)

    attachment = Attachment(
        tenant_id=auth.tenant_id,
        repair_job_id=repair_job_id,
        watch_id=watch_id,
        shoe_repair_job_id=shoe_repair_job_id,
        auto_key_job_id=auto_key_job_id,
        uploaded_by_user_id=auth.user_id,
        storage_key=storage_key,
        file_name=safe_name,
        content_type=content_type,
        file_size_bytes=file_size,
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
    dl_token: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    tenant_id: UUID
    user_id: UUID
    if dl_token:
        tenant_id, user_id, token_storage_key = _decode_signed_download_token(dl_token)
        if token_storage_key != storage_key:
            raise HTTPException(status_code=401, detail="Invalid download token")
    else:
        token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else None
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        try:
            claims = decode_access_token(token)
            tenant_id = claims.tenant_id
            user_id = claims.user_id
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
    try:
        dest = attachment_storage.resolve_existing_path(storage_key)
    except InvalidStorageKeyError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    except AttachmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(dest), filename=attachment.file_name or storage_key, media_type=attachment.content_type or "application/octet-stream")


@router.get("/download-link/{storage_key:path}")
def create_download_link(
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

    token = _create_signed_download_token(
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        storage_key=storage_key,
    )
    return {
        "download_url": f"/v1/attachments/download/{quote(storage_key, safe='')}" f"?dl_token={quote(token, safe='')}",
        "expires_in_seconds": SIGNED_DOWNLOAD_EXPIRE_SECONDS,
    }


@router.get("", response_model=list[AttachmentRead])
def list_attachments(
    repair_job_id: UUID | None = None,
    watch_id: UUID | None = None,
    shoe_repair_job_id: UUID | None = None,
    auto_key_job_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(Attachment).where(Attachment.tenant_id == auth.tenant_id)
    if repair_job_id:
        query = query.where(Attachment.repair_job_id == repair_job_id)
    if watch_id:
        query = query.where(Attachment.watch_id == watch_id)
    if shoe_repair_job_id:
        query = query.where(Attachment.shoe_repair_job_id == shoe_repair_job_id)
    if auto_key_job_id:
        query = query.where(Attachment.auto_key_job_id == auto_key_job_id)

    sort_fields = {
        "created_at": Attachment.created_at,
        "file_name": Attachment.file_name,
        "file_size_bytes": Attachment.file_size_bytes,
    }
    sort_col = sort_fields.get(sort_by)
    if sort_col is None:
        raise HTTPException(status_code=400, detail="Invalid sort_by")
    if sort_dir.lower() not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Invalid sort_dir")
    query = query.order_by(sort_col.asc() if sort_dir.lower() == "asc" else sort_col.desc())
    query = query.offset(offset).limit(limit)

    rows = session.exec(query).all()
    return [AttachmentRead(**row.model_dump()) for row in rows]
