# Sentry Critical Workflow Alerts

This project emits `CRITICAL_WORKFLOW_FAILURE` events from API middleware when key customer-facing workflows return `4xx` or `5xx`.

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
