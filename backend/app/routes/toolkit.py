"""Mobile Services toolkit: tool catalogue, per-tenant selections, scenario recommendations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_feature, require_tech_or_above
from ..models import Tenant

router = APIRouter(prefix="/v1/toolkit", tags=["toolkit"])

_CATALOG_PATH = Path(__file__).parent.parent.parent / "seed" / "mobile_services_tools.json"
with open(_CATALOG_PATH, encoding="utf-8") as _f:
    _CATALOG: dict[str, Any] = json.load(_f)

_TOOL_INDEX: dict[str, dict] = {}
for _group in _CATALOG.get("groups", []):
    _gid = _group["id"]
    _glabel = _group["label"]
    for _tool in _group.get("tools", []):
        _TOOL_INDEX[_tool["key"]] = {**_tool, "group_id": _gid, "group_label": _glabel}

_SCENARIO_BY_ID = {s["id"]: s for s in _CATALOG.get("scenarios", [])}


def _parse_selected(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return [str(x) for x in data if isinstance(x, (str, int))]
    except json.JSONDecodeError:
        return []


def _user_has_tool(selected: set[str], tool_key: str, alternatives_map: dict[str, list[str]]) -> bool:
    if tool_key in selected:
        return True
    for alt in alternatives_map.get(tool_key) or []:
        if alt in selected:
            return True
    return False


class ToolkitSelectionUpdate(BaseModel):
    tool_keys: list[str] = Field(default_factory=list, max_length=500)


class MobileNotificationsRead(BaseModel):
    customer_sms_enabled: bool


class MobileNotificationsPatch(BaseModel):
    customer_sms_enabled: bool


@router.get("/mobile-notifications", response_model=MobileNotificationsRead)
def get_mobile_notifications(
    auth: AuthContext = Depends(get_auth_context),
    _f=Depends(require_feature("auto_key")),
    session: Session = Depends(get_session),
):
    """Whether this shop sends SMS to customers for mobile services (auto key) jobs."""
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return MobileNotificationsRead(
        customer_sms_enabled=bool(getattr(tenant, "mobile_services_customer_sms_enabled", True)),
    )


@router.patch("/mobile-notifications", response_model=MobileNotificationsRead)
def patch_mobile_notifications(
    body: MobileNotificationsPatch,
    auth: AuthContext = Depends(require_tech_or_above),
    _f=Depends(require_feature("auto_key")),
    session: Session = Depends(get_session),
):
    """Enable or disable customer-facing SMS for mobile services (does not affect tech reminders)."""
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant.mobile_services_customer_sms_enabled = body.customer_sms_enabled
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return MobileNotificationsRead(customer_sms_enabled=bool(tenant.mobile_services_customer_sms_enabled))


@router.get("/catalog")
def get_toolkit_catalog(_auth: AuthContext = Depends(get_auth_context), _f=Depends(require_feature("auto_key"))):
    """Full tool groups + scenarios (read-only)."""
    return {
        "title": _CATALOG.get("title", "Toolkit"),
        "description": _CATALOG.get("description", ""),
        "groups": _CATALOG.get("groups", []),
        "scenarios": [{"id": s["id"], "label": s["label"], "tips": s.get("tips", "")} for s in _CATALOG.get("scenarios", [])],
    }


@router.get("/my-selection")
def get_my_toolkit_selection(
    auth: AuthContext = Depends(get_auth_context),
    _f=Depends(require_feature("auto_key")),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    keys = _parse_selected(tenant.toolkit_selected_keys)
    valid = [k for k in keys if k in _TOOL_INDEX]
    return {"tool_keys": valid}


@router.put("/my-selection")
def put_my_toolkit_selection(
    body: ToolkitSelectionUpdate,
    auth: AuthContext = Depends(get_auth_context),
    _f=Depends(require_feature("auto_key")),
    session: Session = Depends(get_session),
):
    unknown = [k for k in body.tool_keys if k not in _TOOL_INDEX]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown tool keys: {', '.join(unknown[:12])}")
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    # Deduplicate preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for k in body.tool_keys:
        if k not in seen:
            seen.add(k)
            ordered.append(k)
    tenant.toolkit_selected_keys = json.dumps(ordered)
    session.add(tenant)
    session.commit()
    return {"tool_keys": ordered}


class ToolkitRecommendBody(BaseModel):
    scenario_id: str = Field(..., min_length=1, max_length=128)


@router.post("/recommend")
def recommend_tools_for_scenario(
    body: ToolkitRecommendBody,
    auth: AuthContext = Depends(get_auth_context),
    _f=Depends(require_feature("auto_key")),
    session: Session = Depends(get_session),
):
    scenario = _SCENARIO_BY_ID.get(body.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Unknown scenario")

    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    selected = set(_parse_selected(tenant.toolkit_selected_keys))
    alts: dict[str, list[str]] = scenario.get("alternatives") or {}
    # normalise alternative values to str list
    alts_norm: dict[str, list[str]] = {}
    for req_key, alt_list in alts.items():
        if isinstance(alt_list, list):
            alts_norm[req_key] = [str(a) for a in alt_list]

    def tool_row(key: str, have: bool) -> dict:
        meta = _TOOL_INDEX.get(key, {})
        return {
            "key": key,
            "name": meta.get("name", key),
            "group_label": meta.get("group_label", ""),
            "have": have,
            "via_alternative": have and key not in selected and any((a in selected) for a in alts_norm.get(key, [])),
        }

    required_keys = list(scenario.get("required") or [])
    nice_keys = list(scenario.get("nice_to_have") or [])

    required_rows = []
    missing_required = []
    for key in required_keys:
        have = _user_has_tool(selected, key, alts_norm)
        row = tool_row(key, have)
        required_rows.append(row)
        if not have:
            missing_required.append(row)

    nice_rows = []
    missing_nice = []
    for key in nice_keys:
        have = key in selected
        row = tool_row(key, have)
        nice_rows.append(row)
        if not have:
            missing_nice.append(row)

    ready = len(missing_required) == 0

    return {
        "scenario_id": scenario["id"],
        "label": scenario["label"],
        "tips": scenario.get("tips", ""),
        "ready_for_required": ready,
        "required": required_rows,
        "nice_to_have": nice_rows,
        "missing_required": missing_required,
        "missing_nice_to_have": missing_nice,
    }
