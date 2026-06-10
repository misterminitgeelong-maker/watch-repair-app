# Two-way SMS (customer texts in Mainspring)

Every job ticket has a **Messages** tab showing the full SMS conversation with
that customer — automated system texts, staff messages, and the customer's
replies. Threads are matched by the customer's phone number, so a reply always
shows up on each of their tickets even if it was logged against a different job
(or before any job existed).

## One-time Twilio setup (required to receive replies)

Outbound SMS only needs `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and
`TWILIO_FROM_NUMBER`. To **receive** customer replies you must also point your
Twilio number at the inbound webhook:

1. Twilio Console → Phone Numbers → your number → **Messaging Configuration**.
2. Under "A message comes in", select **Webhook**, method **HTTP POST**.
3. Set the URL to:

   ```
   https://<your PUBLIC_BASE_URL host>/v1/webhook/sms/incoming
   ```

   e.g. `https://mainspring.au/v1/webhook/sms/incoming`

Without this, customer replies go nowhere — Twilio receives them but never
forwards them to Mainspring.

## How inbound texts are routed

1. The sender's number is matched to a customer (AU formats normalised, e.g.
   `+61412345678` ↔ `0412 345 678`).
2. The message is attached to their most recent open job (watch / shoe /
   mobile services) when one exists; otherwise it's saved unlinked and still
   appears on their tickets via phone matching.
3. An **Inbox** alert (`customer_sms_reply`) is raised either way.
4. Unknown numbers are ignored.

## YES / NO quote approvals by text

The watch-repair quote SMS invites the customer to "Reply YES to approve or NO
to decline". A reply of YES / NO (also Y, N, APPROVE, DECLINE) while a quote is
awaiting a decision records the approval or decline exactly like the web link —
job moves to go-ahead / no-go, the decision is logged, and the customer gets a
confirmation text back.

## Quote reminders

Quotes (watch repair and mobile services) with no customer decision after
`QUOTE_REMINDER_DAYS` (default 7) get one automatic reminder SMS. For watch
quotes the reminder refreshes the approval link, so it works for another full
`QUOTE_APPROVAL_TOKEN_TTL_HOURS` window even if the original link expired.
Reminders run from an in-app scheduler (every
`QUOTE_REMINDER_CHECK_INTERVAL_MINUTES`); `POST /v1/quotes/send-reminders`
triggers a run for your tenant manually. Reminder texts appear in the job's
Messages tab like any other system SMS.
