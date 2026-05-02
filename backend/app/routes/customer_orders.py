from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
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
