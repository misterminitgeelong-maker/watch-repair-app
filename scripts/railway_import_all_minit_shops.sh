#!/usr/bin/env bash
# Bulk-import all Mister Minit shops from TSS xlsx into the linked Railway environment.
# Prereqs: npx, Node, Python deps in backend/, `npx @railway/cli login`, `npx @railway/cli link`
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
XLSX="${MINIT_TSS_XLSX:-$HOME/Downloads/TSS Dec25 Report (1).xlsx}"
if [[ ! -f "$XLSX" ]]; then
  echo "XLSX not found: $XLSX" >&2
  echo "Set MINIT_TSS_XLSX to your workbook path." >&2
  exit 1
fi
cd "$ROOT/backend"
RAILWAY="npx --yes @railway/cli"
echo "==> Dry-run against production DB (--check-db)"
$RAILWAY run -- python scripts/import_minit_shops_from_xlsx.py \
  --input "$XLSX" --check-db --verbose
echo "==> Apply import (--apply)"
$RAILWAY run -- python scripts/import_minit_shops_from_xlsx.py \
  --input "$XLSX" --apply --verbose
