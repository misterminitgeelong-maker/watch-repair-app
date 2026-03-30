"""Vehicle key / immobiliser hints from seed data (Locksmith Master Vehicle_Systems derived)."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from ..dependencies import AuthContext, get_auth_context, require_feature

router = APIRouter(prefix="/v1/vehicle-key-specs", tags=["vehicle-key-specs"])

_SPEC_PATH = Path(__file__).parent.parent.parent / "seed" / "vehicle_key_specs.json"
_ENTRIES: list[dict[str, Any]] = []
if _SPEC_PATH.is_file():
    with open(_SPEC_PATH, encoding="utf-8") as _f:
        _RAW = json.load(_f)
        _ENTRIES = list(_RAW.get("entries") or [])


def _norm(s: str | None) -> str:
    if not s:
        return ""
    return unicodedata.normalize("NFKC", s).strip().lower()


def _combine_tech_notes(e: dict[str, Any]) -> str:
    lines: list[str] = []
    for label, key in (
        ("Immobiliser", "immobiliser_family"),
        ("Transponder / system", "transponder_system"),
        ("AKL complexity", "akl_complexity"),
        ("Likely method", "likely_method"),
        ("Region", "region"),
    ):
        v = e.get(key)
        if isinstance(v, str) and v.strip():
            lines.append(f"{label}: {v.strip()}")
    notes = e.get("typical_notes")
    if isinstance(notes, str) and notes.strip():
        lines.append(notes.strip())
    return "\n".join(lines)


def _display_model(e: dict[str, Any]) -> str:
    model = str(e.get("model") or "").strip()
    var = e.get("variant")
    if isinstance(var, str) and var.strip():
        return f"{model} ({var.strip()})"
    return model


def _label(e: dict[str, Any]) -> str:
    y = e.get("years_label") or ""
    kt = e.get("key_type") or ""
    chip = e.get("transponder_system") or ""
    tail = " · ".join(x for x in (y, kt, chip) if x)
    return f"{e.get('make')} {_display_model(e)} · {tail}".strip()


def _score(entry: dict[str, Any], make_q: str, model_q: str, year: int | None) -> int:
    score = 0
    em = _norm(str(entry.get("make") or ""))
    ecomb = _norm(str(entry.get("model") or "") + " " + str(entry.get("variant") or ""))

    if make_q:
        if em == make_q:
            score += 120
        elif em.startswith(make_q):
            score += 90
        elif make_q in em:
            score += 60
        else:
            return -1
    if model_q:
        if model_q in ecomb:
            score += 80
        elif any(part and part in ecomb for part in model_q.split()):
            score += 40
        else:
            return -1
    elif make_q:
        # make only — prefer shorter model names for quick picking
        score += 5

    yf, yt = entry.get("year_from"), entry.get("year_to")
    if year is not None and isinstance(yf, int) and isinstance(yt, int):
        if yf <= year <= yt:
            score += 50
        else:
            score -= 40

    return score


@router.get("/search")
def search_vehicle_key_specs(
    make: str = Query("", max_length=80, description="Vehicle make (partial ok)"),
    model: str = Query("", max_length=120, description="Vehicle model (partial ok)"),
    year: int | None = Query(None, ge=1900, le=2100),
    limit: int = Query(12, ge=1, le=30),
    _auth: AuthContext = Depends(get_auth_context),
    _f=Depends(require_feature("auto_key")),
):
    """Rank Vehicle_Systems rows for workshop ticket auto-fill (Mobile Services)."""
    make_q = _norm(make)
    model_q = _norm(model)
    if len(make_q) < 2 and len(model_q) < 2:
        return {"matches": []}

    ranked: list[tuple[int, dict[str, Any]]] = []
    for e in _ENTRIES:
        sc = _score(e, make_q, model_q, year)
        if sc > 0:
            ranked.append((sc, e))

    ranked.sort(key=lambda x: -x[0])
    matches: list[dict[str, Any]] = []
    for sc, e in ranked[:limit]:
        dm = _display_model(e)
        yf, yt = e.get("year_from"), e.get("year_to")
        vn = e.get("key_type")
        cs = e.get("transponder_system")
        matches.append(
            {
                "score": sc,
                "label": _label(e),
                "vehicle_make": str(e.get("make") or "").strip(),
                "vehicle_model": dm,
                "year_from": yf,
                "year_to": yt,
                "years_label": e.get("years_label"),
                "key_type": vn if isinstance(vn, str) else None,
                "chip_type": cs if isinstance(cs, str) else None,
                "tech_notes": _combine_tech_notes(e),
            }
        )

    return {"matches": matches}
