# Data Breach Response Runbook (Mainspring)

> **DRAFT. Requires legal review before it is relied on.** It summarises the
> Australian Notifiable Data Breaches (NDB) scheme (Privacy Act 1988, Part IIIC)
> as an engineering checklist. Who is the "entity" with notification duties
> (Mainspring as platform operator, each franchisee, or both) must be confirmed
> by a lawyer. Do not treat this document as legal advice.

## 1. Contain (hour 0 to 24)

1. Name an incident lead and open an incident log (time, who, what, decisions). Keep it factual.
2. Stop the bleed: revoke or rotate the exposed credential or token.
   - Staff sessions: bump the user's token version / deactivate the user; rotate `JWT_SECRET` if signing keys leaked (signs everyone out).
   - Customer capability links (quote, status, invoice, portal): rotate the affected tokens (`quote_approval_token`, `status_token`, `customer_view_token`, `PortalSession`).
   - Third parties: rotate Twilio, SendGrid, Xero, Stripe, storage and database credentials; Railway/Sentry/log-access reviews.
3. Preserve evidence before cleaning up: snapshot the database, export the relevant log windows (Railway, Sentry), do not delete rows.
4. Disable the affected feature or tenant if needed (`Tenant.is_active = false`).

## 2. Assess (target: complete within 30 days of suspicion; sooner is better)

The NDB scheme requires a reasonable and expeditious assessment, and at most 30 days, of whether an eligible data breach occurred (unauthorised access or disclosure, or loss, of personal information likely to result in serious harm).

Work out: **what** data, **whose**, **when**, **how**, and whether harm is likely (ID documents, contact details with addresses, financial data and tokens raise the risk). Remedial action that removes the likelihood of serious harm can mean the breach is not notifiable; record why.

### Pulling "who / what / when" from our records

All queries are scoped per tenant (`tenant_id`) and to the incident window.

| Question | Source | Notes |
| --- | --- | --- |
| Which staff actions touched data (job, customer, quote, user, export, API key changes) | `TenantEventLog` (`actor_user_id`, `actor_email`, `entity_type`, `event_type`, `created_at`) | Bulk exports are logged as `event_type = 'data_export'`. Refresh-token reuse as `refresh_token_reuse`. Customer portal approvals as `quote_*_portal`. |
| Which customers were sent SMS, with what content, and delivery state | `SmsLog` (recipient, body, status, provider SID, timestamps) | Shows who received links containing capability tokens. |
| Which customers were emailed (quotes, invoices, portal links) | `EmailLog` | Same purpose for email. |
| Customer messages and portal activity | `JobMessage`, `PortalSession` | Portal sessions show which email addresses accessed which jobs. |
| Request-level evidence (IP, path, timing) | Railway request log, Sentry | Public-link tokens are redacted in our logs from this release; older logs may contain full tokens, so treat them as exposed if log access was compromised. |
| Data subjects in scope | `Customer`, `Watch`/`Shoe`/`AutoKeyJob`, attachments (ID images) for the affected tenant(s) | Count individuals and list the data categories per person. |

Known gaps to state honestly in the assessment: the audit log has no IP/user-agent and does not record reads of customer records (only exports and writes); git history of this repository contains a customer CSV removed in the privacy-basics change.

## 3. Notify (if an eligible data breach)

1. Prepare the statement for the **OAIC** (Office of the Australian Information Commissioner): entity identity and contact details, description of the breach, kinds of information involved, recommended steps for individuals. Use the OAIC online NDB form.
2. Notify affected **individuals** (or those at risk) as soon as practicable after the OAIC statement, directly (email/SMS), or publish the statement if direct contact is not practicable.
3. Tell the affected franchisee(s) and Minit HQ under the contract, regardless of whether the statutory threshold is met.
4. Consider other duties: payment card scheme or Stripe notification, police/ACSC (cyber.gov.au) report, insurer, and any overseas regime if non-AU individuals are affected.

## 4. Review (within 2 weeks of closure)

- Blameless post-incident review: root cause, timeline, what detection was missing.
- Fix and track actions (access, logging coverage, encryption of stored tokens/IDs).
- Update this runbook and the data inventory. Re-test the evidence queries above.

## Contacts (fill in)

- Incident lead: ____  Backup: ____
- Legal counsel: ____
- OAIC NDB form: https://www.oaic.gov.au/privacy/notifiable-data-breaches
- Hosting (Railway), email (SendGrid), SMS (Twilio), error tracking (Sentry) support contacts: ____
