# Testing Account

## Demo login (with prompts)

Use the **Demo login** to test all features with made-up data—no real customer or job data is used. This flow shows the welcome modal and page tutorials.

1. Go to `/login`
2. Click **"Launch Interactive Demo"** or use `/login?demo=1`
3. Log in with the demo credentials (pre-filled)

Uses a dedicated demo tenant with seeded data: customers, watch/shoe/auto-key jobs, invoices.

## Testing login (no prompts)

For internal QA and breaking things without tutorial pop-ups or guided tours, use a **dedicated testing account**.

### Setup

1. **Backend** – add to `backend/.env`:
   ```env
   TESTING_TENANT_SLUG=testing
   TESTING_OWNER_EMAIL=you@example.com
   TESTING_OWNER_PASSWORD=your-secure-password
   ```

2. **Frontend** – add to `frontend/.env` (or root `.env`):
   ```env
   VITE_TESTING_TENANT_SLUG=testing
   VITE_TESTING_EMAIL=you@example.com
   VITE_TESTING_PASSWORD=your-secure-password
   ```

3. Restart backend and frontend. The testing tenant is created at startup. Rebuild the frontend after changing env vars.

### Use

1. Go to `/login` or `/login?testing=1`
2. Click **"Testing Login (no prompts)"**
3. Seeded data is created if missing; you land on the dashboard with no modals or tutorials

The testing account uses the same seed data as the demo tenant but **demo mode is off**, so you can explore and test without prompts.

## Environment variables (optional)

**Demo credentials** (for the public demo flow):

- `VITE_DEMO_TENANT_SLUG` — demo shop slug (default: `myshop`)
- `VITE_DEMO_EMAIL` — demo login email (default: `admin@admin.com`)
- `VITE_DEMO_PASSWORD` — demo login password (default: `Admin`)

**Testing credentials** (only shown when all three are set):

- `VITE_TESTING_TENANT_SLUG`, `VITE_TESTING_EMAIL`, `VITE_TESTING_PASSWORD`

The backend `seed_demo_data` endpoint is called on both demo and testing login and creates customers, watches, shoe jobs, auto key jobs, and invoices when they're missing.
