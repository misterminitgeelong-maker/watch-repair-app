# Deploying WatchRepair Atelier

Everything is production-ready. Pick whichever option suits you best.

---

## Option A — Railway (easiest, ~$5/mo)

1. Push your code to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Railway auto-detects the Dockerfile and builds it
4. Add a **PostgreSQL** plugin from the Railway dashboard
5. Set environment variables in the Railway service settings:

   | Variable | Value |
   |----------|-------|
   | `DATABASE_URL` | *(auto-filled by the Postgres plugin)* |
   | `JWT_SECRET` | Random 64-char string: `openssl rand -hex 32` |
   | `CORS_ORIGINS` | `https://your-app.up.railway.app` |
   | `PUBLIC_BASE_URL` | `https://your-app.up.railway.app` |
   | `STATIC_DIR` | `/app/static` |

6. Deploy → your app is live at `https://your-app.up.railway.app`
7. Open the URL and **bootstrap** your shop account via login

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
your-domain.com {
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
curl -X POST https://YOUR-DOMAIN/v1/auth/bootstrap \
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

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `sqlite:///./watch_repair.db` | PostgreSQL connection string for production |
| `JWT_SECRET` | **Yes** | `change-me-in-production` | Random secret for signing JWTs |
| `JWT_EXPIRE_MINUTES` | No | `480` | Token lifetime (8 hours) |
| `STATIC_DIR` | Yes (prod) | *(empty)* | Path to built frontend (`/app/static` in Docker) |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed origins |
| `PUBLIC_BASE_URL` | No | `http://localhost:5173` | Used in SMS approval links |
| `TWILIO_ACCOUNT_SID` | No | *(empty)* | Twilio SID for SMS notifications |
| `TWILIO_AUTH_TOKEN` | No | *(empty)* | Twilio auth token |
| `TWILIO_FROM_NUMBER` | No | *(empty)* | Twilio sender number (E.164) |

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
