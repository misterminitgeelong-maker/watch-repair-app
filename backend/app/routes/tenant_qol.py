"""QoL APIs: notification prefs, integration health, customer merge, bulk ops, API keys, webhooks."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlmodel import Session, delete, func, select

from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_tech_or_above
from ..models import (
    AutoKeyJob,
    Customer,
    Invoice,
    RepairJob,
    Shoe,
    ShoeRepairJob,
    SmsLog,
    Tenant,
    TenantApiKey,
    TenantWebhookSubscription,
    UserNotificationPreference,
    Watch,
)
from ..security import hash_password

router = APIRouter(prefix="/v1", tags=["tenant-qol"])


# ── Notification preferences ───────────────────────────────────────────────────

_NOTIFICATION_PREF_FIELDS = (
    "email_quote_approved",
    "email_invoice_paid",
    "email_sms_reply",
    "email_daily_digest",
    "email_weekly_sales_report",
    "email_monthly_sales_report",
)


class NotificationPrefsRead(BaseModel):
    email_quote_approved: bool
    email_invoice_paid: bool
    email_sms_reply: bool
    email_daily_digest: bool
    email_weekly_sales_report: bool
    email_monthly_sales_report: bool
    last_weekly_sales_report_sent_at: datetime | None
    last_monthly_sales_report_sent_at: datetime | None


class NotificationPrefsUpdate(BaseModel):
    email_quote_approved: bool | None = None
    email_invoice_paid: bool | None = None
    email_sms_reply: bool | None = None
    email_daily_digest: bool | None = None
    email_weekly_sales_report: bool | None = None
    email_monthly_sales_report: bool | None = None


def _get_or_create_prefs(session: Session, auth: AuthContext) -> UserNotificationPreference:
    row = session.exec(
        select(UserNotificationPreference)
        .where(UserNotificationPreference.tenant_id == auth.tenant_id)
        .where(UserNotificationPreference.user_id == auth.user_id)
    ).first()
    if row:
        return row
    row = UserNotificationPreference(tenant_id=auth.tenant_id, user_id=auth.user_id)
    session.add(row)
    session.flush()
    return row


def _prefs_read(p: UserNotificationPreference) -> NotificationPrefsRead:
    return NotificationPrefsRead(
        **{field: getattr(p, field) for field in _NOTIFICATION_PREF_FIELDS},
        last_weekly_sales_report_sent_at=p.last_weekly_sales_report_sent_at,
        last_monthly_sales_report_sent_at=p.last_monthly_sales_report_sent_at,
    )


@router.get("/me/notification-preferences", response_model=NotificationPrefsRead)
def get_notification_preferences(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    p = _get_or_create_prefs(session, auth)
    session.commit()
    return _prefs_read(p)


@router.patch("/me/notification-preferences", response_model=NotificationPrefsRead)
def patch_notification_preferences(
    payload: NotificationPrefsUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    p = _get_or_create_prefs(session, auth)
    for field in _NOTIFICATION_PREF_FIELDS:
        val = getattr(payload, field)
        if val is not None:
            setattr(p, field, val)
    p.updated_at = datetime.now(timezone.utc)
    session.add(p)
    session.commit()
    session.refresh(p)
    return _prefs_read(p)


# ── Integration health ─────────────────────────────────────────────────────────

class IntegrationHealthRead(BaseModel):
    twilio_configured: bool
    last_sms_sent_at: str | None
    last_sms_failed_at: str | None
    stripe_configured: bool
    stripe_connect_ready: bool | None
    sendgrid_configured: bool
    attachment_backend: str


@router.get("/tenant/integration-health", response_model=IntegrationHealthRead)
def integration_health(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    last_sent = session.exec(
        select(SmsLog.created_at)
        .where(SmsLog.tenant_id == auth.tenant_id)
        .where(SmsLog.status == "sent")
        .order_by(SmsLog.created_at.desc())
        .limit(1)
    ).first()
    last_fail = session.exec(
        select(SmsLog.created_at)
        .where(SmsLog.tenant_id == auth.tenant_id)
        .where(SmsLog.status != "sent")
        .order_by(SmsLog.created_at.desc())
        .limit(1)
    ).first()
    return IntegrationHealthRead(
        twilio_configured=bool(settings.twilio_account_sid and settings.twilio_auth_token),
        last_sms_sent_at=last_sent.isoformat() if last_sent else None,
        last_sms_failed_at=last_fail.isoformat() if last_fail else None,
        stripe_configured=bool(settings.stripe_secret_key),
        stripe_connect_ready=getattr(tenant, "stripe_connect_charges_enabled", None) if tenant else None,
        sendgrid_configured=bool(getattr(settings, "sendgrid_api_key", None)),
        attachment_backend=settings.attachment_storage_backend,
    )


# ── Customer merge ─────────────────────────────────────────────────────────────

class CustomerMergeRequest(BaseModel):
    primary_customer_id: UUID
    duplicate_customer_id: UUID


@router.post("/customers/merge", status_code=204)
def merge_customers(
    payload: CustomerMergeRequest,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    if payload.primary_customer_id == payload.duplicate_customer_id:
        raise HTTPException(status_code=400, detail="Cannot merge a customer into itself")
    primary = session.get(Customer, payload.primary_customer_id)
    dup = session.get(Customer, payload.duplicate_customer_id)
    if not primary or primary.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Primary customer not found")
    if not dup or dup.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Duplicate customer not found")

    for watch in session.exec(select(Watch).where(Watch.customer_id == dup.id)).all():
        watch.customer_id = primary.id
        session.add(watch)
    for shoe in session.exec(select(Shoe).where(Shoe.customer_id == dup.id)).all():
        shoe.customer_id = primary.id
        session.add(shoe)
    session.exec(
        update(AutoKeyJob)
        .where(AutoKeyJob.tenant_id == auth.tenant_id)
        .where(AutoKeyJob.customer_id == dup.id)
        .values(customer_id=primary.id)
    )
    session.delete(dup)
    session.commit()
    return Response(status_code=204)


# ── Bulk auto-key status ───────────────────────────────────────────────────────

class BulkStatusRequest(BaseModel):
    job_ids: list[UUID] = Field(min_length=1, max_length=100)
    status: str = Field(max_length=64)


@router.post("/auto-key-jobs/bulk-status", status_code=204)
def bulk_auto_key_status(
    payload: BulkStatusRequest,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    jobs = session.exec(
        select(AutoKeyJob)
        .where(AutoKeyJob.tenant_id == auth.tenant_id)
        .where(AutoKeyJob.id.in_(payload.job_ids))
    ).all()
    if len(jobs) != len(payload.job_ids):
        raise HTTPException(status_code=404, detail="One or more jobs not found")
    for job in jobs:
        job.status = payload.status
        session.add(job)
    session.commit()
    return Response(status_code=204)


# ── Export repair jobs CSV ─────────────────────────────────────────────────────

@router.get("/repair-jobs/export.csv")
def export_repair_jobs_csv(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
    limit: int = Query(default=5000, le=10000),
):
    from fastapi.responses import PlainTextResponse

    jobs = session.exec(
        select(RepairJob)
        .where(RepairJob.tenant_id == auth.tenant_id)
        .order_by(RepairJob.created_at.desc())
        .limit(limit)
    ).all()
    lines = ["job_number,title,status,priority,created_at"]
    for j in jobs:
        lines.append(
            f"{j.job_number},{_csv_cell(j.title)},{j.status},{j.priority},{j.created_at.isoformat()}"
        )
    return PlainTextResponse("\n".join(lines), media_type="text/csv")


def _csv_cell(s: str) -> str:
    s = (s or "").replace('"', '""')
    return f'"{s}"' if "," in s else s


# ── API keys ───────────────────────────────────────────────────────────────────

class ApiKeyCreateRequest(BaseModel):
    name: str = Field(max_length=120)


class ApiKeyCreateResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    api_key: str  # shown once


class ApiKeyRead(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime


@router.get("/tenant/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(TenantApiKey).where(TenantApiKey.tenant_id == auth.tenant_id).order_by(TenantApiKey.created_at.desc())
    ).all()
    return [ApiKeyRead(id=r.id, name=r.name, key_prefix=r.key_prefix, is_active=r.is_active, created_at=r.created_at) for r in rows]


@router.post("/tenant/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
def create_api_key(
    payload: ApiKeyCreateRequest,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    raw = f"msk_{secrets.token_urlsafe(32)}"
    prefix = raw[:12]
    row = TenantApiKey(
        tenant_id=auth.tenant_id,
        name=payload.name.strip(),
        key_prefix=prefix,
        key_hash=hash_password(raw),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return ApiKeyCreateResponse(id=row.id, name=row.name, key_prefix=prefix, api_key=raw)


@router.delete("/tenant/api-keys/{key_id}", status_code=204)
def revoke_api_key(
    key_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    row = session.get(TenantApiKey, key_id)
    if not row or row.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="API key not found")
    session.delete(row)
    session.commit()
    return Response(status_code=204)


# ── Webhooks ───────────────────────────────────────────────────────────────────

class WebhookCreateRequest(BaseModel):
    url: str = Field(max_length=512)
    event_types: list[str] = Field(min_length=1)


class WebhookRead(BaseModel):
    id: UUID
    url: str
    event_types: str
    is_active: bool
    created_at: datetime


@router.get("/tenant/webhooks", response_model=list[WebhookRead])
def list_webhooks(
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(TenantWebhookSubscription)
        .where(TenantWebhookSubscription.tenant_id == auth.tenant_id)
        .order_by(TenantWebhookSubscription.created_at.desc())
    ).all()
    return [WebhookRead(id=r.id, url=r.url, event_types=r.event_types, is_active=r.is_active, created_at=r.created_at) for r in rows]


@router.post("/tenant/webhooks", response_model=WebhookRead, status_code=201)
def create_webhook(
    payload: WebhookCreateRequest,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    row = TenantWebhookSubscription(
        tenant_id=auth.tenant_id,
        url=payload.url.strip(),
        event_types=",".join(payload.event_types),
        secret=secrets.token_hex(16),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return WebhookRead(id=row.id, url=row.url, event_types=row.event_types, is_active=row.is_active, created_at=row.created_at)


@router.delete("/tenant/webhooks/{hook_id}", status_code=204)
def delete_webhook(
    hook_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    row = session.get(TenantWebhookSubscription, hook_id)
    if not row or row.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    session.delete(row)
    session.commit()
    return Response(status_code=204)


# ── Job templates & custom fields ──────────────────────────────────────────────

import json

JOB_TEMPLATES: list[dict] = [
    {
        "id": "watch_standard_service",
        "label": "Standard service",
        "module": "watch",
        "title": "Service & pressure test",
        "pre_quote_cents": 15000,
    },
    {
        "id": "watch_battery",
        "label": "Battery replacement",
        "module": "watch",
        "title": "Battery replacement",
        "pre_quote_cents": 4500,
    },
    {
        "id": "auto_key_duplicate",
        "label": "Duplicate key",
        "module": "auto_key",
        "title": "Duplicate key — cut & program",
        "pre_quote_cents": 8900,
    },
    {
        "id": "shoe_resole",
        "label": "Full resole",
        "module": "shoe",
        "title": "Full resole",
        "pre_quote_cents": 12000,
    },
]


class JobTemplateRead(BaseModel):
    id: str
    label: str
    module: str
    title: str
    pre_quote_cents: int


@router.get("/job-templates", response_model=list[JobTemplateRead])
def list_job_templates():
    return [JobTemplateRead(**t) for t in JOB_TEMPLATES]


class CustomFieldsUpdate(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)


@router.patch("/repair-jobs/{job_id}/custom-fields")
def patch_repair_job_custom_fields(
    job_id: UUID,
    payload: CustomFieldsUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(RepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    job.custom_fields_json = json.dumps(payload.fields)
    session.add(job)
    session.commit()
    return {"ok": True, "fields": payload.fields}


@router.patch("/auto-key-jobs/{job_id}/custom-fields")
def patch_auto_key_custom_fields(
    job_id: UUID,
    payload: CustomFieldsUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    job.custom_fields_json = json.dumps(payload.fields)
    session.add(job)
    session.commit()
    return {"ok": True, "fields": payload.fields}


@router.patch("/shoe-repair-jobs/{job_id}/custom-fields")
def patch_shoe_custom_fields(
    job_id: UUID,
    payload: CustomFieldsUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    job.custom_fields_json = json.dumps(payload.fields)
    session.add(job)
    session.commit()
    return {"ok": True, "fields": payload.fields}
