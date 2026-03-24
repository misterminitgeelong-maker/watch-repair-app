# Dungeons-and-drivers

This repository now includes a beginner-friendly starting point for your **Mainspring watch repair SaaS platform**.

## What is included

- Product plan: `WATCH_REPAIR_APP_PLAN.md`
- Initial schema SQL: `docs/watch_repair_schema.sql`
- MVP OpenAPI draft: `docs/watch_repair_openapi.yaml`
- Prioritized backlog + AI prompts: `docs/IMPLEMENTATION_BACKLOG.md`
- Production launch runbook: `docs/MAINSPRING_LAUNCH_CHECKLIST.md`
- Runnable backend starter: `backend/`

## Quick start (first thing to run)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open: `http://127.0.0.1:8000/docs`

## What works now

- Tenant bootstrap + owner account creation
- Login that returns a bearer token
- Create/list/get customers (tenant-isolated)
- Create/list watches (tenant-isolated)
- Create/list repair jobs and update status with history (tenant-isolated)

- Draft/send quotes with line-item totals and public approve/decline links
- Generate invoices from approved quotes and capture manual payments
- Work logs and technician notes linked to repair jobs
- Attachment metadata + signed URL placeholders for upload/download
