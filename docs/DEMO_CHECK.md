# Demo: Victorian B2B Customer Accounts

If Customer Accounts shows "nothing" or errors:

## 1. Restart the backend
Stop any running backend (Ctrl+C) and start fresh:
```bash
cd backend
# or from project root:
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## 2. Verify backend state
Open http://localhost:8000/v1/debug/demo-status

You should see:
```json
{"demo_tenant":{"slug":"myshop","plan_code":"pro"},"customer_account_count":20}
```

If `customer_account_count` is 0, the DB may be empty or a different file. Check `DATABASE_URL` in `.env`.

## 3. Demo login
- Go to /login
- Click **Try Demo**
- Open **Customer Accounts** in the sidebar

You should see 20 Victorian B2B accounts (Pickles, SG Fleet, Hertz, etc.).

## 4. If you still see nothing
- Open DevTools (F12) → Network tab. Check if `/v1/customer-accounts` returns 200 or an error.
- If 500: ensure backend has latest code (git pull) and was restarted.
- If 403: plan/feature issue. Demo tenant should have plan `pro`.
