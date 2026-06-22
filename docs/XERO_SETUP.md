# Xero Integration Setup

Complete setup guide for the Mainspring → Xero integration. Covers app
registration, OAuth connection, invoice sync, online payments, and the
paid-status webhook.

---

## 1. Create the Xero App

1. Go to **developer.xero.com → My Apps → New app**.
2. **Integration type: Web app** (not Mobile/PKCE — the backend authenticates
   with a client secret, which only works with standard auth-code flow).
3. **Company or application URL:** `https://mainspring.au`
4. **OAuth 2.0 redirect URI:** `https://mainspring.au/v1/billing/xero/callback`
   (exact — no trailing slash, no `www`).
5. AI training → **No**, security requirements → **Yes**, accept terms.
6. Click **Create app**.

## 2. Enable Granular Scopes

Xero apps use granular scopes. The old broad `accounting.transactions` scope
does **not** exist on this model. In your app's **Configuration → Scopes**,
ensure these are enabled:

- `accounting.invoices` (create/read invoices — NOT `.read` only)
- `accounting.contacts` (find/create contacts — NOT `.read` only)
- `offline_access` is requested at authorize time for refresh tokens

The backend requests: `offline_access accounting.invoices accounting.contacts`

If you see `invalid_scope` errors, the scope list is the first thing to check.

## 3. Credentials → Railway

From the app's Configuration page, copy:
- **Client ID** (not secret — safe to reference)
- **Client Secret** (generate one; only shown once — treat as a credential)

Add to **Railway → service → Variables**:

```
XERO_CLIENT_ID=<client id>
XERO_CLIENT_SECRET=<client secret>
XERO_REDIRECT_URI=https://mainspring.au/v1/billing/xero/callback
```

Redeploy the service.

## 4. Connect in the App

1. Log in as an **owner**.
2. Go to **Accounts** → the **Accounting (Xero)** card appears when Xero is
   configured server-side.
3. Click **Connect Xero** → authorise in Xero → pick your organisation.
4. The card flips to **connected**.

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| No Xero card in Accounts | `XERO_*` env vars not set or service not redeployed | Add vars, redeploy |
| `invalid_scope` on Xero authorize | Granular scopes not enabled on the app | Enable `accounting.invoices` + `accounting.contacts` in app config |
| `redirect_uri` error on Xero | URI in Xero app doesn't match exactly | Must be `https://mainspring.au/v1/billing/xero/callback` |
| "Could not reach Xero" on Connect click | Server can't read the env vars | Confirm vars are on the correct Railway service |

## 5. Invoice Sync

Once connected, invoices are **pushed to Xero automatically** when created from
an approved quote — both watch/shoe repair invoices and mobile/auto-key invoices.

- Invoices are created as **AUTHORISED** in Xero.
- A Xero contact is found-or-created from the customer (or B2B account).
- Line items come from the quote; tax type and account code default to the
  tenant's Xero settings (or `200` / `OUTPUT`).
- The Xero-hosted **"view & pay online" URL** is fetched and stored so the app's
  invoice email includes a **Pay online** button and the invoice detail page
  shows a **"Pay online (Xero)"** link.
- Each invoice shows its sync status (synced / failed / pending) with a
  **Retry** button.

## 6. Online Payments (Xero → GoCardless / Stripe)

So customers can pay via the Xero invoice's Pay Now button:

1. In Xero: **Settings → Payment services** → connect a provider (GoCardless,
   Stripe, etc.).
2. In Xero: **Settings → Invoice settings** → edit your branding theme → tick
   the payment service. *This step is the one people miss* — a payment service
   does nothing until attached to the theme.

The Pay Now button appears on Xero-hosted invoice pages. The app's invoice email
links to that page via the "View & pay online" CTA.

## 7. Webhook (Paid/Voided Status Sync)

So the app automatically marks invoices **paid** when payment is received in
Xero (e.g. via GoCardless):

1. In your Xero app → **Webhooks → Create webhook:**
   - Event: **Invoices**
   - Delivery URL: `https://mainspring.au/v1/webhooks/xero`
2. Copy the **webhook signing key**.
3. In Railway, add `XERO_WEBHOOK_KEY=<signing key>` and **redeploy**. Wait for
   the deploy to finish.
4. Back in Xero, click **"Send 'Intent to receive'"**. It should turn green.

**Order matters:** the endpoint must have the key deployed *before* Xero sends
the validation request. If validation fails, redeploy and retry.

The webhook handles both repair invoices and mobile/auto-key invoices. It does
not backfill invoices paid before setup — only future payments trigger it.

### Verify the webhook is ready

```bash
curl -s -X POST -o /dev/null -w "HTTP %{http_code}" \
  -H "Content-Type: application/json" -d '{}' \
  https://mainspring.au/v1/webhooks/xero
```

- `401` = key is set, signature rejected (correct — ready for Xero)
- `503` = key not set yet (add `XERO_WEBHOOK_KEY` and redeploy)

## Architecture Summary

```
Invoice created (app)
  → POST /Invoices to Xero (auto, best-effort)
  → GET /Invoices/{id}/OnlineInvoice → store pay URL
  → Invoice email includes "View & pay online" CTA

Customer pays via GoCardless (Xero)
  → Xero fires webhook to POST /v1/webhooks/xero
  → App marks invoice paid

Manual reconciliation
  → Mark invoice paid in Xero manually
  → Same webhook flow → app marks paid
```
