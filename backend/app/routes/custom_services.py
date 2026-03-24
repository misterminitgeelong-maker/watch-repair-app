"""CRUD for tenant custom services (watch/shoe)."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_tech_or_above
from ..models import CustomService, CustomServiceCreate, CustomServiceUpdate

router = APIRouter(prefix="/v1/custom-services", tags=["custom-services"])


def _to_catalogue_item(s: CustomService) -> dict:
    """Convert to same shape as watch/shoe catalogue items for picker consumption."""
    return {
        "key": f"custom__{s.id}",
        "name": s.name,
        "price": s.price_cents / 100,
        "price_cents": s.price_cents,
        "pricing_type": s.pricing_type,
        "group_id": s.group_id,
        "group_label": s.group_label,
        "notes": s.notes,
    }


@router.get("", response_model=list[dict])
def list_custom_services(
    service_type: Optional[str] = Query(default=None, description="Filter: watch | shoe"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """List custom services for the tenant. Returns catalogue-item-shaped dicts."""
    q = select(CustomService).where(CustomService.tenant_id == auth.tenant_id)
    if service_type:
        q = q.where(CustomService.service_type == service_type)
    rows = session.exec(q.order_by(CustomService.name)).all()
    return [_to_catalogue_item(r) for r in rows]


@router.post("", response_model=dict, status_code=201)
def create_custom_service(
    payload: CustomServiceCreate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    """Create a custom service. service_type must be 'watch' or 'shoe'."""
    if payload.service_type not in ("watch", "shoe"):
        raise HTTPException(status_code=400, detail="service_type must be 'watch' or 'shoe'")
    s = CustomService(tenant_id=auth.tenant_id, **payload.model_dump())
    session.add(s)
    session.commit()
    session.refresh(s)
    return _to_catalogue_item(s)


@router.get("/{service_id}", response_model=dict)
def get_custom_service(
    service_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Get a single custom service by id."""
    s = session.get(CustomService, service_id)
    if not s or s.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Custom service not found")
    return _to_catalogue_item(s)


@router.patch("/{service_id}", response_model=dict)
def update_custom_service(
    service_id: UUID,
    payload: CustomServiceUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    """Update a custom service."""
    s = session.get(CustomService, service_id)
    if not s or s.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Custom service not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    session.add(s)
    session.commit()
    session.refresh(s)
    return _to_catalogue_item(s)


@router.delete("/{service_id}", status_code=204)
def delete_custom_service(
    service_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    """Delete a custom service."""
    s = session.get(CustomService, service_id)
    if not s or s.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Custom service not found")
    session.delete(s)
    session.commit()
