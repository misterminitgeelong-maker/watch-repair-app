"""
Build backend/seed/mobile_services_tools.json from Locksmith Master Database xlsx.

Expects sheets Tool_Catalog and Job_Tool_Matrix (optional Equipment_by_Job_Type for tips).

Usage (from repo root or backend):
  python scripts/generate_mobile_services_tools_from_xlsx.py --input "path/to/file.xlsx"
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

REQUIRED_ROLES = (
    "Key Cutting Machine(s)",
    "Primary Programming Tool",
)
NICE_ROLES = (
    "Backup Programming Tool",
    "Diagnostic / Scan Tools",
    "Bench / EEPROM Tools",
)


def _key_cutting_sort_tuple(tool_name: str, tool_category: str) -> tuple[int, str]:
    cat_l = (tool_category or "").lower()
    if "reader" in cat_l or "software" in cat_l:
        return (2, tool_name)
    if "cutting" in cat_l:
        return (0, tool_name)
    return (1, tool_name)


def _ordered_tool_keys_for_role(
    sub: pd.DataFrame,
    role: str,
    name_to_key: dict[str, str],
) -> list[str]:
    cols = ["Tool Name", "Tool Category"] if "Tool Category" in sub.columns else ["Tool Name"]
    role_sub = sub.loc[sub["Role in Job"] == role, cols].copy()
    if role_sub.empty:
        return []
    role_sub["Tool Name"] = role_sub["Tool Name"].dropna().astype(str).str.strip()
    if "Tool Category" not in role_sub.columns:
        role_sub["Tool Category"] = ""
    role_sub["Tool Category"] = role_sub["Tool Category"].fillna("").astype(str)
    role_sub = role_sub[role_sub["Tool Name"].isin(name_to_key)]
    if role == "Key Cutting Machine(s)":
        role_sub["_rk"] = role_sub.apply(
            lambda r: _key_cutting_sort_tuple(r["Tool Name"], r["Tool Category"]),
            axis=1,
        )
        role_sub = role_sub.sort_values(by=["_rk", "Tool Name"])
    else:
        role_sub = role_sub.sort_values(by="Tool Name")
    out: list[str] = []
    seen: set[str] = set()
    for n in role_sub["Tool Name"]:
        k = name_to_key[n]
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def slugify(label: str, used: set[str], max_len: int = 64) -> str:
    s = unicodedata.normalize("NFKC", str(label or ""))
    s = (
        s.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "item"
    if len(s) > max_len:
        s = s[:max_len].rstrip("_")
    base = s
    n = 2
    while s in used:
        suf = f"_{n}"
        s = (base[: max_len - len(suf)]).rstrip("_") + suf
        n += 1
    used.add(s)
    return s


def tool_notes(row: pd.Series) -> str:
    parts = []
    for col in ("Primary Strength", "Typical Use Case", "Notes"):
        if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
            parts.append(str(row[col]).strip())
    return " · ".join(parts) if parts else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to Locksmith_Master_Database_*.xlsx")
    ap.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent.parent / "seed" / "mobile_services_tools.json"),
        help="Output JSON path",
    )
    args = ap.parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)

    tc = pd.read_excel(in_path, sheet_name="Tool_Catalog")
    jm = pd.read_excel(in_path, sheet_name="Job_Tool_Matrix")
    try:
        eq = pd.read_excel(in_path, sheet_name="Equipment_by_Job_Type")
        tips_by_job: dict[str, str] = {}
        for _, row in eq.iterrows():
            jc = row.get("Job Category")
            notes = row.get("Notes")
            if pd.isna(jc):
                continue
            key = str(jc).strip()
            if pd.notna(notes) and str(notes).strip():
                tips_by_job[key] = str(notes).strip()
    except ValueError:
        tips_by_job = {}

    used_keys: set[str] = set()
    name_by_key: dict[str, str] = {}
    tools_by_category: dict[str, list[dict]] = defaultdict(list)

    for _, row in tc.iterrows():
        tname = row.get("Tool Name")
        if pd.isna(tname) or not str(tname).strip():
            continue
        tname = str(tname).strip()
        cat = row.get("Category")
        cat_label = str(cat).strip() if pd.notna(cat) else "Uncategorised"
        tkey = slugify(tname, used_keys, max_len=80)
        name_by_key[tkey] = tname
        note = tool_notes(row)
        tools_by_category[cat_label].append({"key": tkey, "name": tname, **({"notes": note} if note else {})})

    # Stable group order: by category name
    groups = []
    group_ids_used: set[str] = set()
    for cat_label in sorted(tools_by_category.keys()):
        gid = slugify(cat_label, group_ids_used, max_len=48)
        groups.append({"id": gid, "label": cat_label, "tools": tools_by_category[cat_label]})

    # Map tool display name -> key (exact)
    name_to_key = {v: k for k, v in name_by_key.items()}

    scenarios: list[dict] = []
    used_scenario_ids: set[str] = set()
    for job_cat in sorted(jm["Job Category"].dropna().unique(), key=lambda x: str(x)):
        job_cat_s = str(job_cat).strip()
        sub = jm[jm["Job Category"] == job_cat]
        required: list[str] = []
        alternatives: dict[str, list[str]] = {}
        nice_to_have: list[str] = []
        seen_req: set[str] = set()

        for role in REQUIRED_ROLES:
            keys = _ordered_tool_keys_for_role(sub, role, name_to_key)
            if not keys:
                continue
            canonical = keys[0]
            if canonical in seen_req:
                continue
            seen_req.add(canonical)
            required.append(canonical)
            if len(keys) > 1:
                alternatives[canonical] = keys[1:]

        req_set = set(required)
        for role in NICE_ROLES:
            names = sub.loc[sub["Role in Job"] == role, "Tool Name"].dropna().astype(str).str.strip()
            keys = sorted({name_to_key[n] for n in names if n in name_to_key})
            if keys and keys[0] not in req_set:
                nice_to_have.append(keys[0])

        scen: dict = {
            "id": slugify(job_cat_s, used_scenario_ids),
            "label": job_cat_s,
            "required": required,
            "nice_to_have": nice_to_have,
            "alternatives": alternatives,
        }
        tip = tips_by_job.get(job_cat_s, "")
        if tip:
            scen["tips"] = tip
        scenarios.append(scen)

    out = {
        "version": 1,
        "title": "Mobile Services toolkit",
        "description": f"Generated from {in_path.name} (Tool_Catalog + Job_Tool_Matrix). Regenerate with scripts/generate_mobile_services_tools_from_xlsx.py.",
        "groups": groups,
        "scenarios": scenarios,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {out_path} — {len(groups)} groups, {sum(len(g['tools']) for g in groups)} tools, {len(scenarios)} scenarios")


if __name__ == "__main__":
    main()
