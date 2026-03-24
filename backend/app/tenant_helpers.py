"""Tenant-scoped lookup helpers. Return None if not found or wrong tenant."""
from uuid import UUID

from sqlmodel import Session

from .models import (
    Customer,
    Invoice,
    Quote,
    RepairJob,
    Watch,
)


def get_tenant_repair_job(session: Session, job_id: UUID, tenant_id: UUID) -> RepairJob | None:
    job = session.get(RepairJob, job_id)
    if not job or job.tenant_id != tenant_id:
        return None
    return job


def get_tenant_customer(session: Session, customer_id: UUID, tenant_id: UUID) -> Customer | None:
    customer = session.get(Customer, customer_id)
    if not customer or customer.tenant_id != tenant_id:
        return None
    return customer


def get_tenant_watch(session: Session, watch_id: UUID, tenant_id: UUID) -> Watch | None:
    watch = session.get(Watch, watch_id)
    if not watch or watch.tenant_id != tenant_id:
        return None
    return watch


def get_tenant_quote(session: Session, quote_id: UUID, tenant_id: UUID) -> Quote | None:
    quote = session.get(Quote, quote_id)
    if not quote or quote.tenant_id != tenant_id:
        return None
    return quote


def get_tenant_invoice(session: Session, invoice_id: UUID, tenant_id: UUID) -> Invoice | None:
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.tenant_id != tenant_id:
        return None
    return invoice
