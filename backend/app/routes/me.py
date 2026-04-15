"""Authenticated `/v1/me/*` helpers (non–parent-account)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select
from zoneinfo import ZoneInfo

from ..database import get_session
from ..dependencies import AuthContext, require_tech_or_above
from ..models import RepairQueueDayState, Tenant

router = APIRouter(prefix="/v1/me", tags=["me"])

_MAX_DONE_IDS = 500


def _shop_date_for_tenant(tenant_tz: str | None) -> str:
    tz_name = (tenant_tz or "").strip() or "Australia/Melbourne"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Australia/Melbourne")
    return datetime.now(tz).date().isoformat()


class RepairQueueDayStats(BaseModel):
    advanced: int = 0
    checkedIn: int = 0
    skipped: int = 0

    @field_validator("advanced", "checkedIn", "skipped")
    @classmethod
    def non_negative(cls, v: int) -> int:
        if v < 0 or v > 50_000:
            raise ValueError("stat out of range")
        return v


class RepairQueueDayUpsert(BaseModel):
    mode: Literal["watch", "shoe"]
    done_ids: list[str] = Field(default_factory=list, max_length=_MAX_DONE_IDS)
    stats: RepairQueueDayStats = Field(default_factory=RepairQueueDayStats)

    @field_validator("done_ids")
    @classmethod
    def uuid_like(cls, ids: list[str]) -> list[str]:
        out: list[str] = []
        for raw in ids:
            s = (raw or "").strip()
            if not s:
                continue
            try:
                UUID(s)
            except ValueError as e:
                raise ValueError(f"invalid job id: {raw!r}") from e
            out.append(s)
        return out


class RepairQueueDayRead(BaseModel):
    shop_date: str
    mode: str
    done_ids: list[str]
    stats: dict[str, int]


def _row_to_read(row: RepairQueueDayState) -> RepairQueueDayRead:
    try:
        done_ids = json.loads(row.done_ids_json or "[]")
        if not isinstance(done_ids, list):
            done_ids = []
    except json.JSONDecodeError:
        done_ids = []
    try:
        stats = json.loads(row.stats_json or "{}")
        if not isinstance(stats, dict):
            stats = {}
    except json.JSONDecodeError:
        stats = {}
    return RepairQueueDayRead(
        shop_date=row.shop_date,
        mode=row.mode,
        done_ids=[str(x) for x in done_ids],
        stats={k: int(v) for k, v in stats.items() if isinstance(v, (int, float))},
    )


@router.get("/repair-queue-day", response_model=RepairQueueDayRead)
def get_repair_queue_day_state(
    mode: Literal["watch", "shoe"] = Query(...),
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    shop_date = _shop_date_for_tenant(tenant.timezone)
    row = session.exec(
        select(RepairQueueDayState).where(
            RepairQueueDayState.tenant_id == auth.tenant_id,
            RepairQueueDayState.user_id == auth.user_id,
            RepairQueueDayState.mode == mode,
            RepairQueueDayState.shop_date == shop_date,
        )
    ).first()
    if not row:
        return RepairQueueDayRead(
            shop_date=shop_date,
            mode=mode,
            done_ids=[],
            stats={"advanced": 0, "checkedIn": 0, "skipped": 0},
        )
    return _row_to_read(row)


@router.put("/repair-queue-day", response_model=RepairQueueDayRead)
def put_repair_queue_day_state(
    payload: RepairQueueDayUpsert,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    shop_date = _shop_date_for_tenant(tenant.timezone)
    stats_dump = payload.stats.model_dump()
    done_json = json.dumps(payload.done_ids)
    stats_json = json.dumps(stats_dump)
    row = session.exec(
        select(RepairQueueDayState).where(
            RepairQueueDayState.tenant_id == auth.tenant_id,
            RepairQueueDayState.user_id == auth.user_id,
            RepairQueueDayState.mode == payload.mode,
            RepairQueueDayState.shop_date == shop_date,
        )
    ).first()
    now = datetime.now(timezone.utc)
    if row:
        row.done_ids_json = done_json
        row.stats_json = stats_json
        row.updated_at = now
        session.add(row)
    else:
        session.add(
            RepairQueueDayState(
                tenant_id=auth.tenant_id,
                user_id=auth.user_id,
                mode=payload.mode,
                shop_date=shop_date,
                done_ids_json=done_json,
                stats_json=stats_json,
                updated_at=now,
            )
        )
    session.commit()
    refreshed = session.exec(
        select(RepairQueueDayState).where(
            RepairQueueDayState.tenant_id == auth.tenant_id,
            RepairQueueDayState.user_id == auth.user_id,
            RepairQueueDayState.mode == payload.mode,
            RepairQueueDayState.shop_date == shop_date,
        )
    ).first()
    if not refreshed:
        raise HTTPException(status_code=500, detail="Failed to persist queue state")
    return _row_to_read(refreshed)


@router.delete("/repair-queue-day", status_code=204, response_class=Response)
def delete_repair_queue_day_state(
    mode: Literal["watch", "shoe"] = Query(...),
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    shop_date = _shop_date_for_tenant(tenant.timezone)
    row = session.exec(
        select(RepairQueueDayState).where(
            RepairQueueDayState.tenant_id == auth.tenant_id,
            RepairQueueDayState.user_id == auth.user_id,
            RepairQueueDayState.mode == mode,
            RepairQueueDayState.shop_date == shop_date,
        )
    ).first()
    if row:
        session.delete(row)
        session.commit()
    return Response(status_code=204)
