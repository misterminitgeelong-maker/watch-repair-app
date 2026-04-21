"""Tenant-scoped lookup helpers.

All helpers return the row if (and only if) it belongs to `tenant_id`.
Return None if not found or wrong tenant.

Implementation note (B-M10): previously these did `session.get(Model, id)`
and then compared `.tenant_id`. That is two conceptual steps — the row is
loaded first and the tenant check is done in Python. Switch to a single
`select(Model).where(Model.id == id, Model.tenant_id == tenant_id)` so
the tenant check is pushed into SQL. It is also a tiny bit safer if
anyone ever wires up row-level security / RLS later — the filter is on
every query.
"""
from uuid import UUID

from sqlmodel import Session, select

from .models import (
    Customer,
    Invoice,
    Quote,
    RepairJob,
    Watch,
)


def get_tenant_repair_job(session: Session, job_id: UUID, tenant_id: UUID) -> RepairJob | None:
    return session.exec(
        select(RepairJob).where(
            RepairJob.id == job_id,
            RepairJob.tenant_id == tenant_id,
        )
    ).first()


def get_tenant_customer(session: Session, customer_id: UUID, tenant_id: UUID) -> Customer | None:
    return session.exec(
        select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id,
        )
    ).first()


def get_tenant_watch(session: Session, watch_id: UUID, tenant_id: UUID) -> Watch | None:
    return session.exec(
        select(Watch).where(
            Watch.id == watch_id,
            Watch.tenant_id == tenant_id,
        )
    ).first()


def get_tenant_quote(session: Session, quote_id: UUID, tenant_id: UUID) -> Quote | None:
    return session.exec(
        select(Quote).where(
            Quote.id == quote_id,
            Quote.tenant_id == tenant_id,
        )
    ).first()


def get_tenant_invoice(session: Session, invoice_id: UUID, tenant_id: UUID) -> Invoice | None:
    return session.exec(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.tenant_id == tenant_id,
        )
    ).first()
