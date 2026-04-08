"""Vehicle key / immobiliser hints from seed data (Locksmith Master Vehicle_Systems + Cutting_Profiles)."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from ..dependencies import AuthContext, get_auth_context, require_feature

router = APIRouter(prefix="/v1/vehicle-key-specs", tags=["vehicle-key-specs"])

_SEED = Path(__file__).parent.parent.parent / "seed"

_SPEC_PATH = _SEED / "vehicle_key_specs.json"
_ENTRIES: list[dict[str, Any]] = []
_KEY_BLANKS: list[dict[str, Any]] = []
if _SPEC_PATH.is_file():
    with open(_SPEC_PATH, encoding="utf-8") as _f:
        _RAW = json.load(_f)
        _ENTRIES = list(_RAW.get("entries") or [])
        _KEY_BLANKS = list(_RAW.get("key_blanks") or [])

# ── Extra seed data from Locksmith Master Database ────────────────────────────
_KNOWN_ISSUES: list[dict[str, Any]] = []
_TOOL_RECS: list[dict[str, Any]] = []
_CUTTING_PROFILES: list[dict[str, Any]] = []

for _path, _target in [
    (_SEED / "known_issues.json", _KNOWN_ISSUES),
    (_SEED / "tool_recommendations.json", _TOOL_RECS),
    (_SEED / "cutting_profiles.json", _CUTTING_PROFILES),
]:
    if _path.is_file():
        with open(_path, encoding="utf-8") as _f:
            _target.extend(json.load(_f).get("entries", []))


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


def _primary_blank_ref(raw: str | None) -> str:
    s = unicodedata.normalize("NFKC", (raw or "")).strip()
    if not s:
        return ""
    part = s.split("/")[0].strip().split(",")[0].strip()
    return part


def _score_blank_for_entry(b: dict[str, Any], entry: dict[str, Any]) -> int:
    hay = _norm(str(b.get("common_makes_models") or ""))
    if not hay:
        return 0
    make = _norm(str(entry.get("make") or ""))
    model = _norm(str(entry.get("model") or ""))
    var_raw = str(entry.get("variant") or "")
    variant = _norm(var_raw)

    sc = 0
    if make and make in hay:
        sc += 65
    if model and model in hay:
        sc += 70
    elif model:
        for piece in hay.replace("/", " ").split():
            if len(piece) > 3 and model in piece:
                sc += 40
                break

    if variant:
        for tok in re.split(r"[/\s,]+", var_raw):
            t = _norm(tok)
            if len(t) >= 2 and t in hay:
                sc += 24

    return sc


def _key_blanks_for_entry(entry: dict[str, Any], limit: int = 5) -> tuple[list[dict[str, Any]], str | None]:
    ranked: list[tuple[int, dict[str, Any]]] = []
    for b in _KEY_BLANKS:
        bs = _score_blank_for_entry(b, entry)
        if bs >= 40:
            ranked.append((bs, b))
    ranked.sort(key=lambda x: -x[0])
    out: list[dict[str, Any]] = []
    for bs, b in ranked[:limit]:
        br = str(b.get("blank_reference") or "").strip()
        out.append(
            {
                "blank_reference": br,
                "primary_code": _primary_blank_ref(br),
                "description": b.get("description"),
                "key_type": b.get("key_type"),
                "machine_profiles": b.get("machine_profiles"),
                "notes": b.get("notes"),
                "match_score": bs,
            }
        )
    suggested = out[0]["primary_code"] if out else None
    return out, suggested


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
        blanks, suggested_blade = _key_blanks_for_entry(e)
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
                "key_blanks": blanks,
                "suggested_blade_code": suggested_blade,
                # Structured flags (v3)
                "akl_complexity": e.get("akl_complexity"),
                "bsu_required": e.get("bsu_required", False),
                "pin_required": e.get("pin_required", False),
                "eeprom_required": e.get("eeprom_required", False),
                "obd_programmable": e.get("obd_programmable", True),
                "dealer_required": e.get("dealer_required", False),
            }
        )

    return {"matches": matches}


# ── Job context: complexity + known issues + tool recs + cutting profiles ──────

def _best_entry_for_vehicle(make: str, model: str, year: int | None) -> dict[str, Any] | None:
    make_q = _norm(make)
    model_q = _norm(model)
    if not make_q and not model_q:
        return None
    best_score = 0
    best: dict[str, Any] | None = None
    for e in _ENTRIES:
        sc = _score(e, make_q, model_q, year)
        if sc > best_score:
            best_score = sc
            best = e
    return best if best_score > 60 else None


def _match_known_issues(make: str, model: str) -> list[dict[str, Any]]:
    make_n = _norm(make)
    if not make_n:
        return []
    model_n = _norm(model)
    results = []
    for issue in _KNOWN_ISSUES:
        im = _norm(str(issue.get("make") or ""))
        if not im or (make_n not in im and im not in make_n):
            continue
        if model_n:
            imod = _norm(str(issue.get("model") or ""))
            if imod and (model_n not in imod and imod not in model_n):
                continue
        results.append({k: v for k, v in issue.items() if v is not None})
    return results


def _match_tool_recommendations(make: str, model: str, job_type: str | None) -> list[dict[str, Any]]:
    make_n = _norm(make)
    model_n = _norm(model)
    job_n = _norm(job_type or "")
    if not make_n and not model_n:
        return []
    results = []
    for rec in _TOOL_RECS:
        if rec.get("row_type") == "SUMMARY":
            continue
        rm = _norm(str(rec.get("make") or ""))
        if make_n and rm and (make_n not in rm and rm not in make_n):
            continue
        if make_n and not rm:
            continue
        if model_n:
            rmod = _norm(str(rec.get("model") or ""))
            if rmod and (model_n not in rmod and rmod not in model_n):
                continue
        if job_n and rec.get("job_type"):
            rjob = _norm(str(rec.get("job_type") or ""))
            if rjob and (job_n not in rjob and rjob not in job_n):
                continue
        pt = rec.get("primary_tool")
        if pt and str(pt).strip() and str(pt).strip() != "—":
            results.append({k: v for k, v in rec.items() if v is not None and str(v).strip() not in ("", "—")})
    return results[:8]


def _match_cutting_profiles(blade_code: str | None) -> list[dict[str, Any]]:
    if not blade_code or not blade_code.strip():
        return []
    # Try each token in the blade code against blank references
    tokens = [_norm(t) for t in re.split(r"[\s/,]+", blade_code) if len(t.strip()) >= 2]
    blade_n = _norm(blade_code)
    results = []
    for cp in _CUTTING_PROFILES:
        br = _norm(str(cp.get("blank_reference") or ""))
        if not br:
            continue
        if blade_n in br or br in blade_n or any(tok and tok in br for tok in tokens):
            results.append({k: v for k, v in cp.items() if v is not None})
    return results


@router.get("/job-context")
def get_vehicle_job_context(
    make: str = Query("", max_length=80),
    model: str = Query("", max_length=120),
    year: int | None = Query(None, ge=1900, le=2100),
    job_type: str | None = Query(None, max_length=120),
    blade_code: str | None = Query(None, max_length=80),
    _auth: AuthContext = Depends(get_auth_context),
    _f=Depends(require_feature("auto_key")),
):
    """Return AKL complexity, known issues, tool recommendations, and cutting profiles for a vehicle."""
    if not make.strip() and not model.strip():
        return {"complexity": None, "known_issues": [], "tool_recommendations": [], "cutting_profiles": []}

    best = _best_entry_for_vehicle(make, model, year)
    complexity = str(best.get("akl_complexity") or "").strip() if best else None

    return {
        "complexity": complexity or None,
        "known_issues": _match_known_issues(make, model),
        "tool_recommendations": _match_tool_recommendations(make, model, job_type),
        "cutting_profiles": _match_cutting_profiles(blade_code),
    }
