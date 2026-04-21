# Deploying Mainspring

Everything is production-ready. Pick whichever option suits you best.

---

## Option A — Railway (easiest, ~$5/mo)

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Railway auto-detects the Dockerfile and builds it
4. Add a **PostgreSQL** plugin from the Railway dashboard
5. Set environment variables in the Railway service settings to the following values:

```env
DATABASE_URL=(auto-filled by the Postgres plugin)
JWT_SECRET=(run: openssl rand -hex 32)
APP_ENV=production
ALLOW_DEV_AUTO_LOGIN=false
CORS_ORIGINS=https://mainspring.au
PUBLIC_BASE_URL=https://mainspring.au
STATIC_DIR=/app/static
```

1. Deploy → your app is live at `https://mainspring.au`
2. Open the URL and **bootstrap** your shop account via login

---

## Option B — Render (free tier available)

1. Push code to GitHub
2. [render.com](https://render.com) → **New Web Service** → connect repo
3. Set **Docker** as the environment
4. Add a **PostgreSQL** database from the Render dashboard
5. Set the same env vars as above (Render provides `DATABASE_URL` for Postgres)
6. Deploy

---

## Option C — VPS with Docker (full control)

```bash
# On your VPS (Ubuntu/Debian)
sudo apt update && sudo apt install -y docker.io docker-compose-v2

# Clone your repo
git clone https://github.com/YOUR_USER/watch-repair-app.git
cd watch-repair-app

# Create your .env from the template
cp .env.example .env
nano .env   # Fill in real values

# Build and start
docker compose up -d --build

# Your app is now at http://YOUR_SERVER_IP:8000
```

Then put **Caddy** or **nginx** in front for HTTPS:

```bash
# Install Caddy (auto-HTTPS with Let's Encrypt)
sudo apt install -y caddy

# /etc/caddy/Caddyfile
mainspring.au {
    reverse_proxy localhost:8000
}

sudo systemctl restart caddy
```

---

## Option D — Fly.io

```bash
# Install flyctl: https://fly.io/docs/flyctl/install/
fly auth login
fly launch            # auto-detects Dockerfile
fly postgres create   # creates a managed Postgres DB
fly secrets set JWT_SECRET=$(openssl rand -hex 32)
fly secrets set CORS_ORIGINS=https://your-app.fly.dev
fly secrets set PUBLIC_BASE_URL=https://your-app.fly.dev
fly secrets set STATIC_DIR=/app/static
fly deploy
```

---

## After Deploying

### 1. Bootstrap your shop account

Open your app URL and log in — if no account exists yet, hit the bootstrap endpoint once:

```bash
curl -X POST https://mainspring.au/v1/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_name": "Your Shop Name",
    "tenant_slug": "yourshop",
    "owner_email": "you@email.com",
    "owner_full_name": "Your Name",
    "owner_password": "a-strong-password"
  }'
```

### 2. Import historical data

Go to **Database** in the sidebar and upload your CSV file.

### 3. Custom domain (optional)

All platforms above support custom domains — just add a CNAME record pointing to your app URL and configure it in the platform dashboard.

---

## Environment Variables Reference

Defaults below come from `backend/app/config.py` (`Settings`). See
`docs/ENV_VARS.md` and `.env.example` for the complete list including
Stripe, Sentry, Google Maps, Twilio, Blue Flag rego lookup, and rate-limit
settings.

- `DATABASE_URL` (required in prod, default `sqlite:///./watch_repair.db`): PostgreSQL connection string.
- `JWT_SECRET` (required, default `change-me-in-production`): random secret for signing JWTs. Production startup fails fast if this is unset or left at the placeholder.
- `ATTACHMENT_SIGNING_SECRET` (optional, default empty → falls back to `JWT_SECRET`): dedicated secret for short-lived attachment download URLs. Set in production.
- `APP_ENV` (optional, default `development`): one of `development` | `test` | `staging` | `production`. `production` enables the config validator and disables the demo-status debug endpoint.
- `JWT_EXPIRE_MINUTES` (optional, default `480`): access-token lifetime (8 hours).
- `JWT_REFRESH_EXPIRE_DAYS` (optional, default `7`): refresh-token lifetime.
- `ALLOW_DEV_AUTO_LOGIN` (optional, default `false`): enables dev helper `/v1/auth/dev-auto-login`. Must remain `false` in production.
- `ALLOW_PUBLIC_BOOTSTRAP` (optional, default `true`): allow anyone to hit `/v1/auth/bootstrap` to create a tenant. Set to `false` after initial deploy.
- `ALLOW_SQLITE_IN_PRODUCTION` (optional, default `false`): break-glass flag for intentionally running on SQLite in prod. Validator blocks SQLite URLs otherwise.
- `STATIC_DIR` (required in prod, default empty): path to built frontend (`/app/static` in Docker).
- `CORS_ORIGINS` (optional, default `https://mainspring.au,https://www.mainspring.au,capacitor://localhost,https://localhost,http://localhost,ionic://localhost`): comma-separated allowlist. The validator blocks `*` in production.
- `PUBLIC_BASE_URL` (optional, default `https://mainspring.au`): base URL used in SMS approval links and the customer portal URL. Validator blocks localhost values in production.
- `PORTAL_SESSION_TTL_DAYS` (optional, default `7`): lifetime of customer-portal bookmarkable sessions.
- `RATE_LIMIT_AUTH_LOGIN` (optional, default `20/minute`): slowapi limit on `/v1/auth/login`.
- `RATE_LIMIT_PUBLIC_CUSTOMER_LOOKUP` (optional, default `30/minute`).
- `RATE_LIMIT_PUBLIC_PORTAL_CREATE` (optional, default `10/minute`).
- `RATE_LIMIT_PUBLIC_PORTAL_SESSION` (optional, default `60/minute`).
- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` (optional, default empty): required for SMS notifications.

---

## Backups

For PostgreSQL in Docker Compose:

```bash
# Backup
docker compose exec db pg_dump -U watchrepair watchrepair > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260310.sql | docker compose exec -T db psql -U watchrepair watchrepair
```

Don't forget to also back up the `/app/uploads` volume (watch photos).
