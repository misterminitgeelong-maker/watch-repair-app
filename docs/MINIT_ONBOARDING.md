# Mister Minit onboarding

Minit does **not** self-register on the public signup page for the corporate / pilot program. **You provision their account** (email, password, slug) via seed scripts or env vars, then hand them login details privately — same as any enterprise customer.

## Account model

| Who | Login slug (Shop ID) | Minit shop # | How they get access |
|-----|----------------------|--------------|---------------------|
| **Minit HQ / support** | `mmsupport` | — | You seed with **their** corporate email + password |
| **Retail shop** (e.g. Chadstone) | `minit-3269` | 3269 | Seeded under parent; can share HQ login via site switcher or separate users later |
| **Mobile operator** (e.g. you) | `minit-mobile-3904` | 3904 | Seeded under parent; operator’s own email optional later |

- **Parent account** owner email = Minit HQ email (controls My Shops, suburb map, bulk import).
- **Shop number** (`3269`, `3904`) is metadata on the tenant — not the login Shop ID.
- **Public signup** (`/signup`) is for independent shops; not used for the Minit rollout.

## Provision Minit HQ (you run this)

Set **their** credentials in Railway / `backend/.env` (do not use test defaults in production):

```env
MINIT_PARENT_ACCOUNT_NAME=Mister Minit
MINIT_HQ_TENANT_SLUG=mmsupport
MINIT_HQ_TENANT_NAME=Mister Minit Support
MINIT_HQ_OWNER_EMAIL=support@misterminit.com.au
MINIT_HQ_OWNER_PASSWORD=<strong password you generate>
```

Then seed once:

```bash
cd backend
python scripts/seed_minit_pilot.py
```

The script prints `hq_tenant_slug` and `hq_owner_email` (password comes from env). Send Minit only what they need:

- **Shop ID:** `mmsupport`
- **Email / password:** what you set above

Optional: `MINIT_SEED_ENABLED=true` on API startup re-applies the same seed idempotently (safe; updates HQ password if env changes).

Ops-only: `POST /v1/auth/ensure-minit-pilot` when `ALLOW_ENSURE_MINIT_PILOT=true` (same as script).

## HQ operations UI

After signing in as **mmsupport** (`minit_hq`), the left sidebar (desktop) or bottom tabs (mobile) show **six items only**: Dashboard, Inbox, Shops, Mobile Services, Reports, Accounts (`data-nav="minit-hq"`). Dashboard is the network operations overview (`/minit/dashboard`).

## Verify production deploy

After pushing to `main`, confirm Railway rebuilt the **single Docker service** (frontend is baked into the image at `/app/static`, not a separate CDN).

1. **API commit** — `curl https://mainspring.au/v1/health` → `git_commit` should match the latest GitHub `main` SHA (full hash).
2. **Frontend build** — View page source on `https://mainspring.au/` → `<meta name="app-build" content="…">` should be the **same** SHA (not `dev`). After login, DevTools → sidebar `<aside data-nav="minit-hq">` when Shop ID is `mmsupport`.
3. **Session flag** — While logged in as HQ, `GET /v1/auth/session` (Bearer token) must include `"is_minit_hq_ui": true`.
4. **If `git_commit` is new but sidebar is old** — Hard refresh, unregister service worker (Application → Service Workers), clear site data, sign in again. If `app-build` stays `dev`, redeploy: Railway → service → **Redeploy** (clear build cache if offered).
5. **Local UI against prod API** — `cd frontend && VITE_API_BASE_URL=https://mainspring.au npm run dev` (omit variable for same-origin local backend).

Railway: one service from repo root `Dockerfile`; `railway.toml` passes `RAILWAY_GIT_COMMIT_SHA` into the Vite build. Manual redeploy: Railway dashboard → your Mainspring service → **Deployments** → **Redeploy** on latest `main`.

Provision a single shop from the UI: **Shops → Add shop** (creates `minit-{shop_number}`, plan `booking_only`). Bulk import still uses the TSS script below.

## What the seed creates (pilot)

| Role | Shop # | Slug | Plan |
|------|--------|------|------|
| HQ | — | `mmsupport` | `minit_hq` (mobile + parent account only) |
| Retail | 3269 Chadstone | `minit-3269` | `booking_only` |
| Retail | 4278 Toowoomba | `minit-4278` | `booking_only` |
| Mobile operator | 3904 | `minit-mobile-3904` | `basic_auto_key` |

Pilot retail/operator sites initially use the **same owner email/password as HQ** so you can test with one login and the site switcher. For production, add per-shop users from **Parent account → Add shop** or extend import to create store-manager emails.

## Bulk import all shops (TSS Excel)

Source (local): `TSS Dec25 Report (1).xlsx`, sheet **TSS Scores** — columns **Shop #**, **Shop Name**, **Area**, **Region**.

```bash
cd backend
# Preview (~379 shops)
python scripts/import_minit_shops_from_xlsx.py --input "C:/path/to/TSS Dec25 Report (1).xlsx"

# After HQ exists
python scripts/import_minit_shops_from_xlsx.py --input "C:/path/to/file.xlsx" --check-db
python scripts/import_minit_shops_from_xlsx.py --input "C:/path/to/file.xlsx" --apply
```

Each shop: slug `minit-{shop_number}`, plan `booking_only`, linked under Minit parent account.

## Dev-only defaults

Repo defaults (`minit-hq@test.mainspring.au` / `MinitPilot2026!`) are for **local dev only**. Production must use Minit’s real email before seeding.

## Security

- Never commit Minit passwords or the TSS `.xlsx`.
- Turn off `ALLOW_ENSURE_MINIT_PILOT` and `MINIT_SEED_ENABLED` in production after initial provision unless you intend automatic re-sync.
