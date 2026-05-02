import csv
import io
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_tech_or_above
from ..models import Customer, CustomerOrder, CustomerOrderCreate, CustomerOrderRead, CustomerOrderUpdate

router = APIRouter(
    prefix="/v1/customer-orders",
    tags=["customer-orders"],
)


def _to_read(order: CustomerOrder, session: Session) -> CustomerOrderRead:
    customer_name: str | None = None
    if order.customer_id:
        customer = session.get(Customer, order.customer_id)
        if customer:
            customer_name = customer.full_name
    data = order.model_dump()
    data["customer_name"] = customer_name
    return CustomerOrderRead(**data)


@router.get("", response_model=list[CustomerOrderRead])
def list_customer_orders(
    status: str | None = Query(default=None),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    q = select(CustomerOrder).where(CustomerOrder.tenant_id == auth.tenant_id)
    if status:
        q = q.where(CustomerOrder.status == status)
    q = q.order_by(CustomerOrder.created_at.desc())
    orders = session.exec(q).all()
    return [_to_read(o, session) for o in orders]


@router.post("", response_model=CustomerOrderRead)
def create_customer_order(
    payload: CustomerOrderCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    order = CustomerOrder(
        tenant_id=auth.tenant_id,
        **payload.model_dump(),
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return _to_read(order, session)


@router.patch("/{order_id}", response_model=CustomerOrderRead)
def update_customer_order(
    order_id: UUID,
    payload: CustomerOrderUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    order = session.get(CustomerOrder, order_id)
    if not order or order.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(order, field, value)
    order.updated_at = datetime.now(timezone.utc)
    session.add(order)
    session.commit()
    session.refresh(order)
    return _to_read(order, session)


@router.delete("/{order_id}", status_code=204)
def delete_customer_order(
    order_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    order = session.get(CustomerOrder, order_id)
    if not order or order.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
    session.delete(order)
    session.commit()


# ── Import ────────────────────────────────────────────────────────────────────

class CustomerOrderImportResult(BaseModel):
    dry_run: bool
    total_rows: int
    imported: int
    skipped: int
    skipped_reasons: dict[str, int]


_VALID_STATUSES = {"to_order", "ordered", "arrived", "notified", "collected"}
_VALID_PRIORITIES = {"normal", "high", "urgent"}


def _normalise(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_")


def _parse_cents(raw: str) -> int:
    raw = raw.strip().lstrip("$").replace(",", "")
    try:
        return max(0, round(float(raw) * 100))
    except (ValueError, TypeError):
        return 0


def _find_customer(session: Session, tenant_id: UUID, name: str, phone: str) -> UUID | None:
    name = name.strip()
    phone = phone.strip()
    if not name and not phone:
        return None
    q = select(Customer).where(Customer.tenant_id == tenant_id)
    if name:
        q = q.where(Customer.full_name == name)
    customers = session.exec(q).all()
    if phone:
        for c in customers:
            if c.phone and c.phone.replace(" ", "") == phone.replace(" ", ""):
                return c.id
    if customers:
        return customers[0].id
    # Create if name provided
    if name:
        new_customer = Customer(tenant_id=tenant_id, full_name=name, phone=phone or None)
        session.add(new_customer)
        session.flush()
        return new_customer.id
    return None


def _read_csv_rows(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]


@router.post("/import", response_model=CustomerOrderImportResult)
def import_customer_orders(
    file: UploadFile = File(...),
    dry_run: bool = Query(default=True),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    content = file.file.read()

    # Parse rows — try openpyxl for Excel, fall back to CSV
    rows: list[dict[str, str]] = []
    filename = (file.filename or "").lower()
    if filename.endswith((".xlsx", ".xlsm", ".xls")):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            ws = wb.active
            headers = [str(c.value or "").strip() for c in next(ws.iter_rows(min_row=1, max_row=1))]
            for row in ws.iter_rows(min_row=2, values_only=True):
                rows.append({headers[i]: str(v or "").strip() for i, v in enumerate(row) if i < len(headers)})
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not read Excel file: {exc}")
    else:
        try:
            rows = _read_csv_rows(content)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not parse CSV: {exc}")

    imported = 0
    skipped = 0
    skipped_reasons: dict[str, int] = {}

    def _skip(reason: str) -> None:
        nonlocal skipped
        skipped += 1
        skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1

    now = datetime.now(timezone.utc)

    for row in rows:
        # Normalise header keys (strip, lowercase, underscores)
        row = {k.strip().lower().replace(" ", "_"): v for k, v in row.items()}

        title = (row.get("title") or row.get("item") or row.get("description") or "").strip()
        if not title:
            _skip("missing title/item")
            continue

        status_raw = _normalise(row.get("status", "") or "to_order")
        status = status_raw if status_raw in _VALID_STATUSES else "to_order"

        priority_raw = _normalise(row.get("priority", "") or "normal")
        priority = priority_raw if priority_raw in _VALID_PRIORITIES else "normal"

        supplier = (row.get("supplier") or "").strip() or None
        notes = (row.get("notes") or row.get("note") or "").strip() or None
        cost_raw = row.get("cost") or row.get("estimated_cost") or row.get("price") or ""
        estimated_cost_cents = _parse_cents(cost_raw)

        customer_name = (row.get("customer") or row.get("customer_name") or "").strip()
        customer_phone = (row.get("phone") or row.get("customer_phone") or "").strip()

        customer_id: UUID | None = None
        if not dry_run:
            customer_id = _find_customer(session, auth.tenant_id, customer_name, customer_phone)

        if not dry_run:
            order = CustomerOrder(
                tenant_id=auth.tenant_id,
                customer_id=customer_id,
                title=title,
                supplier=supplier,
                status=status,
                priority=priority,
                estimated_cost_cents=estimated_cost_cents,
                notes=notes,
                created_at=now,
                updated_at=now,
            )
            session.add(order)

        imported += 1

    if not dry_run:
        session.commit()

    return CustomerOrderImportResult(
        dry_run=dry_run,
        total_rows=len(rows),
        imported=imported,
        skipped=skipped,
        skipped_reasons=skipped_reasons,
    )
