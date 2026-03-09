# Backend Starter (Beginner Friendly)

## 1) Create a virtual environment
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

## 2) Install dependencies
```bash
pip install -r requirements.txt
```

## 3) Run the API
```bash
uvicorn app.main:app --reload --port 8000
```

## 4) Open API docs
- Docs UI: `http://127.0.0.1:8000/docs`
- Health: `GET http://127.0.0.1:8000/v1/health`

## 5) First setup flow (copy/paste)

### A) Create first tenant + owner
`POST /v1/auth/bootstrap`
```json
{
  "tenant_name": "Timekeepers",
  "tenant_slug": "timekeepers",
  "owner_email": "owner@timekeepers.test",
  "owner_full_name": "Main Owner",
  "owner_password": "supersecret123"
}
```

### B) Login
`POST /v1/auth/login`
```json
{
  "tenant_slug": "timekeepers",
  "email": "owner@timekeepers.test",
  "password": "supersecret123"
}
```

### C) Use Bearer token
In Swagger docs, click **Authorize** and paste:
```text
Bearer <your_access_token>
```

### D) Create a customer and watch
- `POST /v1/customers`
- `POST /v1/watches`
- `GET /v1/customers`
- `GET /v1/watches`
- `POST /v1/repair-jobs`
- `GET /v1/repair-jobs`
- `POST /v1/repair-jobs/{job_id}/status`
- `GET /v1/repair-jobs/{job_id}/status-history`

### E) Quotes
- `POST /v1/quotes`
- `POST /v1/quotes/{quote_id}/send`
- `POST /v1/public/quotes/{token}/decision`

### F) Invoicing + Payments
- `POST /v1/invoices/from-quote/{quote_id}`
- `GET /v1/invoices/{invoice_id}`
- `POST /v1/invoices/{invoice_id}/payments`

### G) Work logs + Attachments
- `POST /v1/work-logs`
- `GET /v1/work-logs?repair_job_id=<id>`
- `POST /v1/attachments`
- `GET /v1/attachments?repair_job_id=<id>`
