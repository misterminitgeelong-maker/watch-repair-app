"""
Generate AU mobile operator suburb routes from nearest-hub distance.

Usage (from backend/):
  python scripts/generate_mobile_territory_routes.py
  python scripts/generate_mobile_territory_routes.py --max-radius-km 80 --conflicts-csv ../seed/minit_mobile_territory_conflicts_au_2026.csv
  python scripts/generate_mobile_territory_routes.py --apply   # generate + import to DB
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.minit_mobile_territory import (  # noqa: E402
    DEFAULT_CONFLICT_GAP_KM,
    DEFAULT_MAX_RADIUS_KM,
    DEFAULT_TERRITORY_OUTPUT,
    generate_territory_routes,
    territory_result_to_dict,
    write_conflicts_csv,
    write_territory_json,
)
from app.minit_shops import DEFAULT_TSS_XLSX_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Minit mobile operator suburb territories (AU)")
    parser.add_argument("--operators-seed", default=None, help="Operator seed JSON path")
    parser.add_argument("--tss", "-i", default=DEFAULT_TSS_XLSX_PATH, help="TSS xlsx path")
    parser.add_argument("--postcodes", default=None, help="Local postcodes CSV (default: download public CSV)")
    parser.add_argument("--output", "-o", default=str(DEFAULT_TERRITORY_OUTPUT), help="Output JSON path")
    parser.add_argument(
        "--conflicts-csv",
        default=None,
        help="Optional CSV path for boundary conflicts (for Minit review)",
    )
    parser.add_argument("--max-radius-km", type=float, default=DEFAULT_MAX_RADIUS_KM)
    parser.add_argument("--conflict-gap-km", type=float, default=DEFAULT_CONFLICT_GAP_KM)
    parser.add_argument("--apply", action="store_true", help="Import generated routes into DB after writing JSON")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    try:
        result = generate_territory_routes(
            operators_seed_path=Path(args.operators_seed) if args.operators_seed else None,
            tss_path=Path(args.tss),
            postcodes_source=Path(args.postcodes) if args.postcodes else None,
            max_radius_km=args.max_radius_km,
            conflict_gap_km=args.conflict_gap_km,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1

    output_path = Path(args.output)
    write_territory_json(result, output_path)
    conflicts_path: Path | None = None
    if args.conflicts_csv:
        conflicts_path = Path(args.conflicts_csv)
        write_conflicts_csv(result, conflicts_path)

    summary = {
        "output_path": str(output_path),
        "conflicts_csv": str(conflicts_path) if conflicts_path else None,
        "operator_hubs": len(result.operators),
        "skipped_operators": result.skipped_operators,
        "route_count": len(result.routes),
        "conflict_count": len(result.conflicts),
        "unassigned_locality_count": result.unassigned_localities,
        "params": result.params,
    }
    if args.verbose:
        print(json.dumps(summary, indent=2), file=sys.stderr)
    else:
        print(json.dumps(summary, indent=2))

    if args.apply:
        from scripts.import_mobile_suburb_routes import import_routes_from_file

        code = import_routes_from_file(output_path, apply=True, verbose=args.verbose)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
