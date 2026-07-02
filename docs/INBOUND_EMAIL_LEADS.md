# Inbound email leads (Mister Minit form BCC)

Mister Minit BCCs their website auto-key enquiry-form emails to a Mainspring
address. SendGrid Inbound Parse converts each email into an HTTP POST to the
app, which stores it and raises an HQ inbox alert for triage.

**Capture-and-triage v1:** no field parsing yet. Emails land in
**Minit HQ → Inbox → Email leads**, a person reads the body and creates the
AutoKey job manually. Once real form templates have been collected, a parser
can promote these straight into routed jobs via the existing suburb-route
logic (`mobile_lead_ingest.py`).

## Endpoint

```
POST /v1/public/inbound-email/{ingest_public_id}?key=<webhook secret>
```

- `ingest_public_id` — the parent account's website-lead ingest id
  (Parent account → Website lead feed; same id as `/v1/public/mobile-key-leads/…`).
- `key` — the same shared webhook secret, passed as a query parameter because
  SendGrid Inbound Parse cannot send custom headers.
- Accepts both Inbound Parse modes: default (parsed `text`/`html`/`headers`
  fields) and "POST the raw, full MIME message" (single `email` field).
- Duplicate `Message-ID`s for the same parent account return
  `{"status": "duplicate"}` without creating a second row (SendGrid retries).
- The HQ inbox alert is raised against the parent account's
  **mobile lead default tenant** — set it before going live
  (`PUT /v1/parent-accounts/me/mobile-lead-ingest/default-tenant`).

## One-time setup

1. **Enable ingest + secret** (as HQ owner, once):
   - `POST /v1/parent-accounts/me/mobile-lead-ingest/enable`
   - `PUT /v1/parent-accounts/me/mobile-lead-ingest/secret` (≥16 chars)
   - `PUT /v1/parent-accounts/me/mobile-lead-ingest/default-tenant`
2. **DNS** — at mainspring.au's DNS host, add an MX record:
   - Host: `leads.mainspring.au`, value `mx.sendgrid.net`, priority `10`.
   - Do **not** reuse a subdomain that already receives normal mail.
3. **SendGrid** — Settings → Inbound Parse → Add Host & URL:
   - Receiving domain: `leads.mainspring.au`
   - Destination URL:
     `https://mainspring.au/v1/public/inbound-email/<ingest_public_id>?key=<webhook secret>`
   - Leave "POST the raw, full MIME message" unticked (parsed mode preferred;
     raw mode also works).
4. **Test** — email anything to `autokey@leads.mainspring.au` and confirm it
   appears in Minit HQ → Inbox → Email leads.
5. **Only then** give Mister Minit the BCC address:
   `autokey@leads.mainspring.au` (any local part on the subdomain works —
   Inbound Parse is a catch-all).

## Triage APIs (HQ owner, multi_site plans)

- `GET /v1/parent-accounts/me/inbound-emails?status=new` — list captured emails
- `GET /v1/parent-accounts/me/inbound-emails/{id}` — full body for reading
- `PATCH /v1/parent-accounts/me/inbound-emails/{id}` — `{"status": "processed" | "dismissed" | "new"}`

## Rollout plan (agreed 2026-07-02)

1. Chadstone-only pilot: default tenant = our own site; work leads manually.
2. Collect real form emails → build the parser against actual templates.
3. Seed the other 25 mobile operators (see `minit_mobile_operators_2026.csv`,
   kept local like the TSS workbooks) with routes configured but **no logins
   issued** until each is flipped live.
4. NZ operators need the ingest state-code validation extended beyond
   `AU_STATES` before auto-routing NZ leads.
