"""Network printer integrations — currently a SAM4S (ESC/POS) receipt printer for intake tickets."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..database import get_session
from ..dependencies import AuthContext, require_tech_or_above
from ..models import Tenant
from ..services.sam4s_printer import (
    DEFAULT_PORT,
    PrinterConnectionError,
    Sam4sTicket,
    build_tickets_escpos,
    send_to_printer,
)

router = APIRouter(prefix="/v1/printers/sam4s", tags=["printers"])


class Sam4sTicketPayload(BaseModel):
    job_number: str
    customer_name: str
    item_title: str
    is_customer_copy: bool
    customer_phone: Optional[str] = None
    services: Optional[str] = None
    date_in: Optional[str] = None
    deposit_label: Optional[str] = None
    balance_label: Optional[str] = None
    qr_url: Optional[str] = None


class Sam4sPrintRequest(BaseModel):
    tickets: list[Sam4sTicketPayload] = Field(min_length=1, max_length=20)


@router.post("/print")
def print_sam4s_tickets(
    payload: Sam4sPrintRequest,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant or not tenant.sam4s_printer_host:
        raise HTTPException(status_code=400, detail="No SAM4S printer configured for this shop yet.")

    tickets = [Sam4sTicket(**t.model_dump()) for t in payload.tickets]
    data = build_tickets_escpos(tickets)

    try:
        send_to_printer(tenant.sam4s_printer_host, tenant.sam4s_printer_port or DEFAULT_PORT, data)
    except PrinterConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"printed": len(tickets)}
