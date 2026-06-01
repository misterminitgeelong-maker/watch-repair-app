"""Read-only Mobile Services pricing catalogue (OEM keys, general services, garage door)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import get_auth_context, require_feature
from ..models import (
    GarageServicingPricing,
    GarageServicingPricingRow,
    OemKeyPricing,
    OemKeyPricingRow,
    ServicePricing,
    ServicePricingRow,
)

router = APIRouter(
    prefix="/v1/mobile-services-pricing",
    tags=["mobile-services-pricing"],
    dependencies=[Depends(require_feature("auto_key"))],
)


def _oem_row(row: OemKeyPricing) -> OemKeyPricingRow:
    return OemKeyPricingRow(
        id=row.id,
        make=row.make,
        model_variant=row.model_variant,
        job_type=row.job_type,
        key_type=row.key_type,
        service_location=row.service_location,
        tool_required=row.tool_required,
        retail_price=row.retail_price,
        is_poa=row.retail_price is None,
        callout_inclusive=row.callout_inclusive,
        notes=row.notes,
    )


def _service_row(row: ServicePricing) -> ServicePricingRow:
    return ServicePricingRow(
        id=row.id,
        category=row.category,
        service_name=row.service_name,
        unit=row.unit,
        retail_price=row.retail_price,
        is_poa=row.retail_price is None,
        callout_inclusive=row.callout_inclusive,
        notes=row.notes,
    )


def _garage_row(row: GarageServicingPricing) -> GarageServicingPricingRow:
    return GarageServicingPricingRow(
        id=row.id,
        service_name=row.service_name,
        description=row.description,
        part_cost_notes=row.part_cost_notes,
        labour_time=row.labour_time,
        retail_price=row.retail_price,
        callout_inclusive=row.callout_inclusive,
        notes=row.notes,
    )


@router.get("/oem-makes", response_model=list[str])
def list_oem_makes(
    _auth=Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(OemKeyPricing.make)
        .where(OemKeyPricing.active == True)  # noqa: E712
        .distinct()
        .order_by(OemKeyPricing.make)
    ).all()
    return list(rows)


@router.get("/oem-keys", response_model=list[OemKeyPricingRow])
def list_oem_keys_by_make(
    make: str = Query(..., min_length=1),
    _auth=Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    make_clean = make.strip()
    if not make_clean:
        raise HTTPException(status_code=400, detail="make is required")
    job_type_order = case(
        (OemKeyPricing.job_type == "Add Key", 0),
        (OemKeyPricing.job_type == "AKL", 1),
        else_=2,
    )
    rows = session.exec(
        select(OemKeyPricing)
        .where(func.lower(OemKeyPricing.make) == make_clean.lower())
        .where(OemKeyPricing.active == True)  # noqa: E712
        .order_by(job_type_order.asc(), OemKeyPricing.model_variant.asc())
    ).all()
    return [_oem_row(r) for r in rows]


@router.get("/services", response_model=list[ServicePricingRow])
def list_service_pricing(
    _auth=Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(ServicePricing)
        .where(ServicePricing.active == True)  # noqa: E712
        .order_by(ServicePricing.category, ServicePricing.service_name)
    ).all()
    return [_service_row(r) for r in rows]


@router.get("/garage", response_model=list[GarageServicingPricingRow])
def list_garage_pricing(
    _auth=Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(GarageServicingPricing)
        .where(GarageServicingPricing.active == True)  # noqa: E712
        .order_by(GarageServicingPricing.service_name)
    ).all()
    return [_garage_row(r) for r in rows]
