# Bulk-import all Mister Minit shops from TSS xlsx via Railway prod DATABASE_URL (runs locally).
# Prereqs: Node/npx, Python backend deps, Railway login + link to mainspring project.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Xlsx = if ($env:MINIT_TSS_XLSX) { $env:MINIT_TSS_XLSX } else { "c:\Users\samme\Downloads\TSS Dec25 Report (1).xlsx" }
if (-not (Test-Path -LiteralPath $Xlsx)) {
  Write-Error "XLSX not found: $Xlsx. Set MINIT_TSS_XLSX or copy the file to Downloads."
}
Set-Location (Join-Path $RepoRoot "backend")
$railway = "npx --yes @railway/cli"
Write-Host "==> Dry-run against production DB (--check-db)"
& npx --yes @railway/cli run -- python scripts/import_minit_shops_from_xlsx.py --input $Xlsx --check-db --verbose
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "==> Apply import (--apply)"
& npx --yes @railway/cli run -- python scripts/import_minit_shops_from_xlsx.py --input $Xlsx --apply --verbose
exit $LASTEXITCODE
