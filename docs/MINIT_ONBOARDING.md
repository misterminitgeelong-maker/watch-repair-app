# Mister Minit onboarding (pilot)

Pilot setup for the Mister Minit parent account, HQ login, retail shop booking sites, and one mobile operator — plus bulk import from the TSS shop spreadsheet.

## Environment

Add to `backend/.env` (or deployment secrets):

```env
MINIT_SEED_ENABLED=true
MINIT_PARENT_ACCOUNT_NAME=Mister Minit
MINIT_HQ_TENANT_SLUG=mister-minit-hq
MINIT_HQ_TENANT_NAME=Mister Minit HQ
MINIT_HQ_OWNER_EMAIL=minit-hq@test.mainspring.au
MINIT_HQ_OWNER_PASSWORD=MinitPilot2026!
```

`MINIT_SEED_ENABLED=true` runs the same pilot seed on API startup (with `STARTUP_SEED_ENABLED` optional). Prefer running the script once in shared environments.

## Pilot sites (created once)

| Role | Shop # | Slug | Plan |
|------|--------|------|------|
| HQ | — | `mister-minit-hq` | `enterprise` |
| Retail | 3269 Chadstone | `minit-3269` | `booking_only` |
| Retail | 4278 Toowoomba | `minit-4278` | `booking_only` |
| Mobile operator | 3904 | `minit-mobile-3904` | `basic_auto_key` |

All child sites share the HQ owner email/password (site switcher in the app).

## Manual seed

```bash
cd backend
python scripts/seed_minit_pilot.py
```

## HQ login

1. Open the web app login.
2. **Tenant slug:** `mister-minit-hq`
3. **Email:** value of `MINIT_HQ_OWNER_EMAIL` (default `minit-hq@test.mainspring.au`)
4. **Password:** value of `MINIT_HQ_OWNER_PASSWORD`

From HQ (enterprise plan), use **Parent account** to view linked sites, create more shops, or link operators.

### Pilot shop login (booking only)

- Slug: `minit-3269` — Chadstone (#3269)
- Same email/password as HQ

### Mobile operator login

- Slug: `minit-mobile-3904` — operator #3904
- Plan: Basic – Mobile Services (`basic_auto_key`)

## Bulk import from TSS Excel

Source file (local; not in repo):  
`c:\Users\samme\Downloads\TSS Dec25 Report (1).xlsx`  
Sheet **TSS Scores**, columns: **Shop #**, **Shop Name**, **Area**, **Region** (no street address — import builds `business_address` from name + area + region).

**Dry-run (default)** — parse-only, no database (always run this first):

```bash
cd backend
python scripts/import_minit_shops_from_xlsx.py --input "C:/Users/samme/Downloads/TSS Dec25 Report (1).xlsx"
```

After pilot seed, dry-run with duplicate detection:

```bash
python scripts/import_minit_shops_from_xlsx.py --input "C:/path/to/file.xlsx" --check-db
```

**Apply** (after pilot/HQ exists):

```bash
python scripts/import_minit_shops_from_xlsx.py --input "C:/path/to/file.xlsx" --seed-pilot --apply
```

- Skips shops whose `shop_number` is already linked under the parent account.
- New tenants use slug `minit-{shop_number}` and plan `booking_only` unless `--plan-code` is set.
- Does **not** import mobile operators from the sheet; operator **3904** is pilot-seeded only.

## Security notes

- Change `MINIT_HQ_OWNER_PASSWORD` before any shared/staging host is exposed.
- Do not commit the TSS `.xlsx` (large, customer data).
- Set `MINIT_SEED_ENABLED=false` in production unless you intend automatic pilot recreation on deploy.
