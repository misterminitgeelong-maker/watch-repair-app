"""Validate core seed files are present and non-empty."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "seed"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []

    required_files = [
        "vehicle_key_specs.json",
        "known_issues.json",
        "tool_recommendations.json",
        "mobile_services_tools.json",
        "job_pricing.json",
        "watch_repairs_catalogue.json",
        "shoe_repairs_catalogue.json",
    ]
    for rel in required_files:
        path = SEED_DIR / rel
        _require(path.is_file(), f"Missing required seed file: {rel}", failures)

    if failures:
        for msg in failures:
            print(f"[seed-sanity] FAIL: {msg}")
        return 1

    vehicle_specs = _load_json(SEED_DIR / "vehicle_key_specs.json")
    vehicle_entries = vehicle_specs.get("entries", [])
    _require(isinstance(vehicle_entries, list) and len(vehicle_entries) > 0, "vehicle_key_specs entries missing", failures)
    declared_count = int(vehicle_specs.get("entry_count") or 0)
    _require(declared_count == len(vehicle_entries), "vehicle_key_specs entry_count does not match entries length", failures)

    known_issues = _load_json(SEED_DIR / "known_issues.json")
    _require(len(known_issues.get("entries", [])) > 0, "known_issues entries missing", failures)

    tool_recs = _load_json(SEED_DIR / "tool_recommendations.json")
    _require(len(tool_recs.get("entries", [])) > 0, "tool_recommendations entries missing", failures)

    mobile_tools = _load_json(SEED_DIR / "mobile_services_tools.json")
    groups = mobile_tools.get("groups", [])
    tool_count = sum(len(group.get("tools", [])) for group in groups if isinstance(group, dict))
    _require(len(groups) > 0 and tool_count > 0, "mobile_services_tools groups/tools missing", failures)

    job_pricing = _load_json(SEED_DIR / "job_pricing.json")
    _require(len(job_pricing.get("entries", [])) > 0, "job_pricing entries missing", failures)

    watch_catalogue = _load_json(SEED_DIR / "watch_repairs_catalogue.json")
    _require(len(watch_catalogue.get("groups", [])) > 0, "watch_repairs_catalogue groups missing", failures)

    shoe_catalogue = _load_json(SEED_DIR / "shoe_repairs_catalogue.json")
    _require(len(shoe_catalogue.get("groups", [])) > 0, "shoe_repairs_catalogue groups missing", failures)

    if failures:
        for msg in failures:
            print(f"[seed-sanity] FAIL: {msg}")
        return 1

    print("[seed-sanity] OK: core seed files are parseable and non-empty.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
