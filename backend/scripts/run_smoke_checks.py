"""Run a focused backend smoke suite for auto-key critical flows."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_auto_key_jobs.py",
        "tests/test_auto_key_contracts.py",
        "tests/test_vehicle_key_specs.py",
        "tests/test_user_delete.py",
    ]
    print("Running smoke suite:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
