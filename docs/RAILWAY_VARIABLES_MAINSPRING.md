# Railway Variables for Mainspring

Use this exact set for the app service in Railway.

```env
APP_ENV=production
ALLOW_DEV_AUTO_LOGIN=false
ALLOW_PUBLIC_BOOTSTRAP=true
JWT_SECRET=<set-a-strong-random-secret>
JWT_EXPIRE_MINUTES=480
CORS_ORIGINS=https://mainspring.au,https://www.mainspring.au
PUBLIC_BASE_URL=https://mainspring.au
STATIC_DIR=/app/static
STARTUP_SEED_ENABLED=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
```

Notes:

- DATABASE_URL is injected automatically by the Railway PostgreSQL plugin.
- Keep ALLOW_PUBLIC_BOOTSTRAP=true only for first owner creation, then set false and redeploy.
- Do not use placeholder values for JWT_SECRET in production.
