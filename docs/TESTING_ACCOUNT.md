# Testing Account

## Demo login (with prompts)

Use the **Demo login** to test all features with made-up data—no real customer or job data is used. This flow shows the welcome modal and page tutorials.

1. Go to `/login`
2. Click **"Launch Interactive Demo"** or use `/login?demo=1`
3. Log in with the demo credentials (pre-filled)

Uses a dedicated demo tenant with seeded data: customers, watch/shoe/auto-key jobs, invoices.

## Testing login (no prompts)

For internal QA and breaking things without tutorial pop-ups or guided tours, use a **dedicated testing account**. Credentials stay in the backend only—there is no button or link that reveals them.

### Setup

Add to `backend/.env` (never commit this file):

```env
TESTING_TENANT_SLUG=testing
TESTING_OWNER_EMAIL=you@example.com
TESTING_OWNER_PASSWORD=your-secure-password
```

Restart the backend. The testing tenant is created at startup. **Do not put these in the frontend**—credentials in `VITE_*` vars get bundled into the public JS.

### Use

1. Go to `/login`
2. Use the normal **Sign in** form and enter your testing Shop ID, email, and password
3. You land on the dashboard with no modals or tutorials

Only you know the credentials. The login page looks the same to everyone—there is no "Testing Login" button.

### Troubleshooting

**Stuck on "Signing in…"**
- Ensure the backend is running (e.g. `uvicorn backend.app.main:app` or `cd backend && uvicorn app.main:app`, typically on port 8000).
- The frontend dev server proxies `/v1` to `http://127.0.0.1:8000`; if you're not using the proxy, the API URL may be wrong.
- If you see "Request timed out", the backend is not reachable. Start it and try again.

**"Invalid shop ID, email, or password"**
- The testing tenant is only created when `TESTING_TENANT_SLUG`, `TESTING_OWNER_EMAIL`, and `TESTING_OWNER_PASSWORD` are set in the backend `.env`.
- `.env` is read from the directory you start the backend from (e.g. `backend/.env` if you run `cd backend && uvicorn app.main:app`).
- Restart the backend after changing `.env`.

## Environment variables (optional)

**Demo credentials** (for the public demo flow):

- `VITE_DEMO_TENANT_SLUG` — demo shop slug (default: `myshop`)
- `VITE_DEMO_EMAIL` — demo login email (default: `admin@admin.com`)
- `VITE_DEMO_PASSWORD` — demo login password (default: `Admin`)

The backend `seed_demo_data` endpoint is called on demo login. For the testing tenant, you can call it once after logging in (e.g. via API) if you want sample data; otherwise the account starts empty.
