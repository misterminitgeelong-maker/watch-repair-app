from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

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
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    q: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    query = select(Customer).where(Customer.tenant_id == auth.tenant_id)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(func.lower(Customer.full_name).like(pattern))
    sort_fields = {
        "created_at": Customer.created_at,
        "full_name": Customer.full_name,
    }
    sort_col = sort_fields.get(sort_by)
    if sort_col is None:
        raise HTTPException(status_code=400, detail="Invalid sort_by")
    if sort_dir.lower() not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Invalid sort_dir")
    query = query.order_by(sort_col.asc() if sort_dir.lower() == "asc" else sort_col.desc())
    query = query.offset(offset).limit(limit)
    return session.exec(query).all()


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
    brand: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_dir: str = Query(default="desc"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    q = select(Watch).where(Watch.tenant_id == auth.tenant_id)
    if customer_id is not None:
        q = q.where(Watch.customer_id == customer_id)
    if brand is not None and brand.strip():
        q = q.where(Watch.brand == brand.strip())
    sort_fields = {
        "created_at": Watch.created_at,
        "brand": Watch.brand,
        "model": Watch.model,
    }
    sort_col = sort_fields.get(sort_by)
    if sort_col is None:
        raise HTTPException(status_code=400, detail="Invalid sort_by")
    if sort_dir.lower() not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Invalid sort_dir")
    q = q.order_by(sort_col.asc() if sort_dir.lower() == "asc" else sort_col.desc())
    q = q.offset(offset).limit(limit)
    return session.exec(q).all()


@router.get("/watches/{watch_id}", response_model=WatchRead)
def get_watch(
    watch_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    watch = session.get(Watch, watch_id)
    if not watch or watch.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Watch not found")
    return watch


COMMON_WATCH_BRANDS = [
    "Rolex", "Omega", "Seiko", "Citizen", "Casio", "Tissot", "Fossil",
    "Michael Kors", "Tag Heuer", "Longines", "Hamilton", "Swatch",
    "Bulova", "Oris", "Breitling", "Cartier", "Patek Philippe", "Audemars Piguet",
    "Timex", "Invicta", "Daniel Wellington", "Movado", "Skagen",
]


@router.get("/watch-brands", response_model=list[str])
def list_watch_brands(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Return distinct watch brands from the database, merged with common brands."""
    watches = session.exec(select(Watch).where(Watch.tenant_id == auth.tenant_id)).all()
    from_db = {w.brand.strip() for w in watches if w.brand and w.brand.strip()}
    combined = sorted(from_db | set(COMMON_WATCH_BRANDS), key=str.lower)
    return combined
