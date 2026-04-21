# Why the Demo Customer Accounts Might Not Show

## The Flow (What Should Happen)

```
1. Backend starts  →  Seeds 20 Victorian B2B accounts for tenant "myshop"
2. You click Try Demo  →  Login with myshop / admin@admin.com / Admin
3. You land on Dashboard  →  Sidebar shows "Customer Accounts" (if plan = pro)
4. You click Customer Accounts  →  Page fetches GET /v1/customer-accounts
5. API returns 20 accounts  →  Page displays them
```

If you see "nothing," one of these steps is failing.

---

## Common Causes

### A. "I don't see Customer Accounts in the sidebar"
**Cause:** Your tenant's plan doesn't include the `customer_accounts` feature.  
**Fix:** Demo tenant (myshop) should have plan `pro`. At startup we set it. If you're on a different tenant (e.g. one you created), it may have a basic plan.

**Check:** After login, open DevTools → Network. Find the request to `/v1/auth/session`. In the response, `enabled_features` should include `"customer_accounts"`. If it doesn't, the plan is wrong.

---

### B. "I see Customer Accounts but the page is empty / loading forever / error"
**Cause:** The API call to list accounts is failing or returning empty.

**Check:** DevTools → Network. When you open Customer Accounts, look for `GET /v1/customer-accounts`:
- **200 with JSON array** → Data is there; a frontend bug may be hiding it.
- **500** → Backend error (we've fixed the Car Auctions one; restart backend to get latest code).
- **403** → Your plan doesn't allow customer_accounts.
- **Failed / No request** → Frontend can't reach backend (wrong URL, backend not running, CORS).

---

### C. "Backend isn't reachable"
**Cause:** Frontend can't talk to the backend.

**Local dev:**  
- Backend must run on **port 8000** (Vite proxies `/v1` to `http://127.0.0.1:8000`).  
- Start with: `cd backend && uvicorn app.main:app --reload --port 8000` (or `python -m uvicorn app.main:app --reload --port 8000` from the `backend/` directory). The app package is `app`, so running from the repo root with `backend.app.main:app` fails because `backend/` is not a Python package.

**Production:**  
- Frontend uses `baseURL: '/v1'` (same origin). Backend must serve both the SPA and `/v1/*` on the same domain.

---

### D. "Backend has old code / wasn't restarted"
**Cause:** The running backend was started before the fixes (Car Auctions, startup seeding, etc.).

**Fix:** Fully stop the backend (Ctrl+C in its terminal, close any duplicates) and start it again. Changes only apply after restart.

---

### E. "Wrong tenant or empty database"
**Cause:** You're logged into a tenant that has no accounts, or the DB is different from what the backend uses.

**Check:** Open `http://localhost:8000/v1/debug/demo-status` (no login needed). You should see:
```json
{"demo_tenant":{"slug":"myshop","plan_code":"pro"},"customer_account_count":20}
```
If `customer_account_count` is 0, the demo tenant has no accounts. Restart the backend so startup seeding runs again.

---

## Quick Diagnostic (Run These)

**1. Is the backend running and seeded?**
```
Open: http://localhost:8000/v1/debug/demo-status
Expect: customer_account_count: 20
```

**2. Can you log in?**
```
Open: http://localhost:8000/docs
Try POST /v1/auth/login with:
  tenant_slug: myshop
  email: admin@admin.com
  password: Admin
Expect: 200 with access_token
```

**3. Does the list work with that token?**
```
Use the token from step 2 as Bearer in GET /v1/customer-accounts
Expect: 200 with array of 20 accounts
```

If step 1 fails → Backend not running or not seeded.  
If step 2 fails → Demo tenant missing or wrong credentials.  
If step 3 fails → Auth or plan/feature issue; check response status and body.

---

## Still Stuck?

Please share:
1. Are you running **locally** (npm run dev + uvicorn) or **deployed** (e.g. mainspring.au)?
2. Do you see **Customer Accounts** in the sidebar after demo login? (Yes / No)
3. When you open Customer Accounts, what do you see? (Empty list / Error message / Loading spinner / Redirect to dashboard)
4. DevTools Network tab: when you open Customer Accounts, what happens to the `/v1/customer-accounts` request? (Status code and brief response if possible)
