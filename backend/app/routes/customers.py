from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import Customer, CustomerCreate, CustomerRead, Watch, WatchCreate, WatchRead

router = APIRouter(prefix="/v1", tags=["customers", "watches"])


@router.post("/customers", response_model=CustomerRead, status_code=201)
def create_customer(
    payload: CustomerCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    customer = Customer(tenant_id=auth.tenant_id, **payload.model_dump())
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


@router.get("/customers", response_model=list[CustomerRead])
def list_customers(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    return session.exec(select(Customer).where(Customer.tenant_id == auth.tenant_id)).all()


@router.get("/customers/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    customer = session.get(Customer, customer_id)
    if not customer or customer.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("/watches", response_model=WatchRead, status_code=201)
def create_watch(
    payload: WatchCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    customer = session.get(Customer, payload.customer_id)
    if not customer or customer.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    watch = Watch(tenant_id=auth.tenant_id, **payload.model_dump())
    session.add(watch)
    session.commit()
    session.refresh(watch)
    return watch


@router.get("/watches", response_model=list[WatchRead])
def list_watches(
    customer_id: Optional[UUID] = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    q = select(Watch).where(Watch.tenant_id == auth.tenant_id)
    if customer_id is not None:
        q = q.where(Watch.customer_id == customer_id)
    return session.exec(q).all()
