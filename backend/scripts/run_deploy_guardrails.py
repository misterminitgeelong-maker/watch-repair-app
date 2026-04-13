"""Run local deploy guardrails in checklist order."""

from __future__ import annotations

import subprocess
import sys


def _run_step(name: str, command: list[str]) -> int:
    print(f"\n[guardrails] {name}")
    print("[guardrails] >", " ".join(command))
    return subprocess.call(command)


def main() -> int:
    steps = [
        ("Seed sanity check", [sys.executable, "scripts/check_seed_sanity.py"]),
        ("Apply migrations (alembic upgrade head)", [sys.executable, "-m", "alembic", "upgrade", "head"]),
        ("Auto-key numbering audit", [sys.executable, "scripts/audit_autokey_numbers.py"]),
        ("Smoke checks", [sys.executable, "scripts/run_smoke_checks.py"]),
    ]

    for name, cmd in steps:
        code = _run_step(name, cmd)
        if code != 0:
            print(f"[guardrails] FAIL: {name} (exit {code})")
            return code

    print("\n[guardrails] OK: all guardrails passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
