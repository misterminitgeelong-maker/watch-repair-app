"""Customer ID and proof-of-ownership record for mobile-services (auto key) jobs.

DRAFT against assumed AASRA-style requirements: the real rules are still to be
confirmed with Minit or a lawyer (docs/aasra-id-capture.md). Every create, edit
and view is written to AutoKeyIdAccessLog. The ID number is encrypted at rest and
only shown in full on an explicit, logged `reveal`.
"""
from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Field, Session, SQLModel, select

from ..database import get_session
from ..dependencies import AuthContext, require_tech_or_above
from ..id_crypto import decrypt_id_number, encrypt_id_number
from ..models import AutoKeyIdAccessLog, AutoKeyIdCapture, AutoKeyJob, TenantEventLog, User

router = APIRouter(prefix="/v1/auto-key-jobs/{job_id}/id-capture", tags=["auto-key-id-capture"])

#: Bump when the wording below changes; the version is stored with each record.
CONSENT_TEXT_VERSION = "2026-11-draft-1"
CONSENT_TEXT = (
    "I confirm the details I have given are true, that I am entitled to have this key or lock "
    "work done on this vehicle, and I agree to the business recording my photo-ID details and "
    "proof of ownership for this job as required for locksmith work."
)

IdType = Literal["drivers_licence", "passport", "other_photo_id"]
OwnershipType = Literal["registration", "purchase_papers", "insurance", "other"]
ConsentMethod = Literal["verbal", "signed"]


class IdCaptureWrite(SQLModel):
    id_type: IdType
    id_number: str = Field(min_length=3, max_length=40)
    id_issuer: Optional[str] = Field(default=None, max_length=64)
    name_on_id: str = Field(min_length=2, max_length=200)
    proof_of_ownership_type: OwnershipType
    proof_of_ownership_notes: Optional[str] = Field(default=None, max_length=500)
    #: The customer has agreed to CONSENT_TEXT; must be true to save.
    consent_given: bool
    consent_method: ConsentMethod


class IdCaptureRead(SQLModel):
    id: UUID
    auto_key_job_id: UUID
    id_type: str
    id_number_masked: str
    #: Full number: only present on a `?reveal=true` read.
    id_number: Optional[str] = None
    id_issuer: Optional[str] = None
    name_on_id: str
    proof_of_ownership_type: str
    proof_of_ownership_notes: Optional[str] = None
    consent_text_version: str
    consent_given_at: datetime
    consent_method: str
    verified_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class IdConsentTextRead(SQLModel):
    version: str
    text: str


class IdAccessLogRead(SQLModel):
    id: UUID
    user_id: UUID
    user_email: Optional[str] = None
    support_actor_user_id: Optional[UUID] = None
    action: str
    created_at: datetime


def _job(session: Session, auth: AuthContext, job_id: UUID) -> AutoKeyJob:
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")
    return job


def _record(session: Session, job_id: UUID) -> Optional[AutoKeyIdCapture]:
    return session.exec(select(AutoKeyIdCapture).where(AutoKeyIdCapture.auto_key_job_id == job_id)).first()


def _access(session: Session, auth: AuthContext, job_id: UUID, action: str) -> None:
    session.add(AutoKeyIdAccessLog(
        tenant_id=auth.tenant_id,
        auto_key_job_id=job_id,
        user_id=auth.user_id,
        support_actor_user_id=auth.support_actor_user_id,
        action=action,
    ))


def _masked(last4: str) -> str:
    return f"••••{last4}"


def _read(row: AutoKeyIdCapture, number: Optional[str] = None) -> IdCaptureRead:
    return IdCaptureRead(
        id=row.id,
        auto_key_job_id=row.auto_key_job_id,
        id_type=row.id_type,
        id_number_masked=_masked(row.id_number_last4),
        id_number=number,
        id_issuer=row.id_issuer,
        name_on_id=row.name_on_id,
        proof_of_ownership_type=row.proof_of_ownership_type,
        proof_of_ownership_notes=row.proof_of_ownership_notes,
        consent_text_version=row.consent_text_version,
        consent_given_at=row.consent_given_at,
        consent_method=row.consent_method,
        verified_by_user_id=row.verified_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def has_id_capture(session: Session, job_id: UUID) -> bool:
    return session.exec(
        select(AutoKeyIdCapture.id).where(AutoKeyIdCapture.auto_key_job_id == job_id)
    ).first() is not None


@router.get("/consent-text", response_model=IdConsentTextRead)
def get_consent_text(
    job_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    _job(session, auth, job_id)
    return IdConsentTextRead(version=CONSENT_TEXT_VERSION, text=CONSENT_TEXT)


@router.get("", response_model=IdCaptureRead)
def get_id_capture(
    job_id: UUID,
    reveal: bool = False,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    _job(session, auth, job_id)
    row = _record(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No ID record for this job")
    number = None
    if reveal:
        number = decrypt_id_number(row.id_number_encrypted)
        if number is None:
            raise HTTPException(status_code=500, detail="The stored ID number could not be decrypted")
    _access(session, auth, job_id, "reveal" if reveal else "view")
    session.commit()
    return _read(row, number)


@router.put("", response_model=IdCaptureRead)
def save_id_capture(
    job_id: UUID,
    payload: IdCaptureWrite,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = _job(session, auth, job_id)
    if not payload.consent_given:
        raise HTTPException(status_code=422, detail="The customer must agree to the ID consent before it can be saved.")
    number = "".join(payload.id_number.split())
    if len(number) < 3:
        raise HTTPException(status_code=422, detail="Enter the ID number.")
    now = datetime.now(timezone.utc)
    row = _record(session, job_id)
    action = "update" if row else "create"
    if row is None:
        row = AutoKeyIdCapture(
            tenant_id=auth.tenant_id,
            auto_key_job_id=job_id,
            id_type=payload.id_type,
            id_number_encrypted="",
            id_number_last4="",
            name_on_id="",
            proof_of_ownership_type=payload.proof_of_ownership_type,
            consent_text_version=CONSENT_TEXT_VERSION,
            consent_given_at=now,
            consent_method=payload.consent_method,
            verified_by_user_id=auth.user_id,
        )
    row.id_type = payload.id_type
    row.id_number_encrypted = encrypt_id_number(number)
    row.id_number_last4 = number[-4:]
    row.id_issuer = (payload.id_issuer or "").strip() or None
    row.name_on_id = payload.name_on_id.strip()
    row.proof_of_ownership_type = payload.proof_of_ownership_type
    row.proof_of_ownership_notes = (payload.proof_of_ownership_notes or "").strip() or None
    row.consent_text_version = CONSENT_TEXT_VERSION
    row.consent_given_at = now
    row.consent_method = payload.consent_method
    row.verified_by_user_id = auth.user_id
    row.updated_at = now
    session.add(row)
    _access(session, auth, job_id, action)
    actor = session.get(User, auth.user_id)
    # The event log carries job/ID facts but never the ID number itself.
    session.add(TenantEventLog(
        tenant_id=auth.tenant_id,
        actor_user_id=auth.user_id,
        actor_email=actor.email if actor else None,
        entity_type="auto_key_job",
        entity_id=job.id,
        event_type="auto_key_id_captured",
        event_summary=f"ID record {'updated' if action == 'update' else 'recorded'} ({payload.id_type.replace('_', ' ')})",
    ))
    session.commit()
    session.refresh(row)
    return _read(row)


@router.get("/access-log", response_model=list[IdAccessLogRead])
def list_id_access_log(
    job_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    _job(session, auth, job_id)
    if auth.role not in ("owner", "manager", "platform_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    rows = session.exec(
        select(AutoKeyIdAccessLog)
        .where(AutoKeyIdAccessLog.auto_key_job_id == job_id)
        .order_by(AutoKeyIdAccessLog.created_at.desc())
        .limit(200)
    ).all()
    emails = {u.id: u.email for u in session.exec(select(User).where(User.id.in_({r.user_id for r in rows}))).all()} if rows else {}
    return [
        IdAccessLogRead(
            id=r.id, user_id=r.user_id, user_email=emails.get(r.user_id),
            support_actor_user_id=r.support_actor_user_id, action=r.action, created_at=r.created_at,
        )
        for r in rows
    ]
