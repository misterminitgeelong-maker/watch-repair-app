# Mobile-job ID capture and support-access consent (DRAFT)

**Status: draft.** The real AASRA / licensing requirements have not been confirmed with Minit or a lawyer. Do not describe this as "AASRA compliant" until they have. Wording and fields below are assumptions to be corrected.

## ID capture (mobile services / auto key jobs)
- `PUT /v1/auto-key-jobs/{id}/id-capture` records ID type, ID number, issuer, name on ID, proof of ownership, and the customer's consent (text version `CONSENT_TEXT_VERSION`, time, verbal/signed). One record per job.
- The ID number is encrypted at rest (Fernet). Set `ID_CAPTURE_KEY` in production; if blank it falls back to `JWT_SECRET`, so rotating that secret would make stored numbers unreadable.
- Reads are masked (last 4). `?reveal=true` returns the full number. Every create, update, view and reveal is written to `AutoKeyIdAccessLog` (viewable by owner/manager at `/id-capture/access-log`).
- A job with an ID record cannot be deleted (409). Cancel it instead.
- Optional per-shop switch (`require_id_capture`, Accounts page): a job cannot move to work-complete without a record. Default off.
- Not built: photo-ID image capture, retention/deletion schedule, audit export, hash-chained status history.

## Support-access consent
- A shop that has taken its own login must be allowed in by its owner: `PUT /v1/shop/support-access` grants a time-boxed window (default 24 h, max 7 days) and can be turned off. Default is off.
- HQ "enter shop" now needs an active grant and a reason (5+ characters). HQ "change login email" needs the grant too. Shops still on the shared HQ-provisioned login are exempt (nothing to consent to yet).
- Audit rows written during a support session are tagged `support_actor_user_id` and end with "[support session]".
- A support session cannot grant itself access. Platform-admin entry is unchanged.
- Not built: owner email/notification on entry, read-only support scope.

## SMS
Mainspring keeps using one shared Twilio number. Per-shop numbers were deliberately not built.
