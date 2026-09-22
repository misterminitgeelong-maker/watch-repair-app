# Sentry Critical Workflow Alerts

This project emits `CRITICAL_WORKFLOW_FAILURE` events from API middleware when key customer-facing workflows return `4xx` or `5xx`, with one exception: see [Spent customer links](#spent-customer-links-not-an-alert) below.

## Prerequisites

- Set backend `SENTRY_DSN`.
- Set frontend `VITE_SENTRY_DSN` (optional but recommended).
- Deploy latest backend so events include the `critical_workflow` tag.

## Tagged workflow types

- `quick_intake_failure` (`/v1/public/auto-key-intake/*`)
- `public_booking_failure` (`/v1/public/auto-key-booking/*`)
- `public_invoice_failure` (`/v1/public/auto-key-invoice/*`)
- `day_before_reminder_failure` (`POST /v1/auto-key-jobs/day-before-reminders`)
- `invoice_update_failure` (`PATCH /v1/auto-key-jobs/invoices/*`)

## Spent customer links (not an alert)

The three public link paths — `auto-key-intake`, `auto-key-booking`, `auto-key-invoice` —
carry single-use tokens sent to customers by SMS. The token is cleared once used
(`submit_public_auto_key_intake` nulls `customer_intake_token`), so **a 404 on these paths
is the designed outcome**, not a failure. It is what a customer gets by re-tapping the SMS
link, refreshing after submitting, opening an old message, or having a carrier or security
product scan the URL. The customer sees "This link is not valid or the job has already been
completed."

A 404 on these three paths is therefore logged as `PUBLIC_LINK_SPENT` at info level and
raises no Sentry event (`_is_spent_public_link` in `backend/app/main.py`). Everything else
on them still alerts, including:

- `5xx` — the intake form is actually broken
- `422` — a request-contract break between the customer page and the API
- `429` — a real customer being rate-limited

A 404 on the operator and cron paths (`day-before-reminders`, `invoices/*`) still alerts;
they have no spent-token case. Covered by `backend/tests/test_critical_workflow_alerts.py`.

If you need to investigate a specific spent link, search the request log for
`PUBLIC_LINK_SPENT` — note that a used token and a token that never existed are
indistinguishable, because the token row is cleared on submit.

## Recommended Alert Rules

Create one alert rule per workflow type for clear ownership.

- **Rule name**: `Critical Workflow - <workflow>`
- **Filter**:
  - `event.type:error`
  - message contains `CRITICAL_WORKFLOW_FAILURE`
  - tag `critical_workflow:<workflow>`
- **Threshold**:
  - `>= 3 events in 10 minutes` for public booking/invoice/intake
  - `>= 2 events in 15 minutes` for invoice update/day-before reminders
- **Actions**:
  - Notify engineering Slack channel
  - Notify on-call email/pager

## Recommended Dashboards

Create dashboard widgets grouped by `critical_workflow`:

- Event count (last 24h)
- Affected endpoints (`request_path`)
- Error status code distribution (`http.status_code`)
- Top environments (`environment`)

Suggested query:

- `message:"CRITICAL_WORKFLOW_FAILURE"`

## Triage Notes

- Check API logs with `request_id` from the Sentry event extras.
- Verify whether failures are auth/config issues (`401`, `403`, `404`) vs server faults (`5xx`).
- For `public_*` spikes, validate token generation and public URL routing first.
