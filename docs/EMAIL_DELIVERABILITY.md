# Transactional email delivery: verified state and deployment

Verified 2 October 2026 (Australia/Sydney).

## Findings

- SendGrid domain authentication ID 31101715 covers mainspring.au and was reverified successfully.
- The current bounce domain is em2336.mainspring.au, not em695.mainspring.au.
- CNAME em2336.mainspring.au -> u107891836.wl087.sendgrid.net (DNS only).
- CNAME s1._domainkey.mainspring.au -> s1.domainkey.u107891836.wl087.sendgrid.net (DNS only).
- CNAME s2._domainkey.mainspring.au -> s2.domainkey.u107891836.wl087.sendgrid.net (DNS only).
- SPF at the bounce CNAME target: v=spf1 include:sendgrid.net ~all.
- Root SPF authorises Google Workspace: v=spf1 include:_spf.google.com ~all. A root SendGrid include is unnecessary for this custom Return-Path.
- DMARC: v=DMARC1; p=quarantine; adkim=r; aspf=r; rua=mailto:dmarc_rua@onsecureserver.net;
- Received SendGrid report dated 28 September: From Mainspring <admin@mainspring.au>, SPF pass (149.72.126.143), DKIM pass (d=mainspring.au; s=s1), DMARC pass with relaxed alignment. This was an archived message, not confirmed junk-folder evidence.
- Safe Browsing Transparency Report: No unsafe content found (report last updated 30 September). A specific token URL or recipient-side warning remains unverified.
- Cloudflare has a potentially mistyped Workspace DKIM hostname google._domainkey._domainkey.mainspring.au. Confirm the configured selector/key in Google Admin before correcting it; this is separate from SendGrid signing.

## Pending app deployment

Do not merge or push to main or change production runtime variables before 18:00 Australia/Sydney on 2 October 2026. Use the isolated codex/mainspring-email-deliverability branch only.

The change removes invalid mailto-only List-Unsubscribe-Post headers and mailing-list headers from transactional messages, disables click and open tracking, adds configurable EMAIL_REPLY_TO_ADDRESS with per-message shop reply precedence, uses a stable Mainspring default sender name and root-domain fallback, and clarifies the invite email/page identity and expiry. GET requests do not consume pending invites; regression coverage fetches an invite twice before successful completion.

Production already sends as admin@mainspring.au, so preserve this verified root-domain sender unless there is a concrete reason to change it. Set EMAIL_FROM_NAME=Mainspring and EMAIL_REPLY_TO_ADDRESS=admin@mainspring.au after the time gate. Environment-variable updates can deploy the app; stage and apply after the gate only. There is no database migration in this change.

Recurring reports have existing application preferences. This patch does not implement RFC 8058 one-click unsubscribe for subscribed/bulk reports; that needs a real HTTPS POST endpoint and classification of eligible messages before advertising it.

## Verification after deployment

1. Check Railway deployment and GitHub CI, then /health.
2. Send a disposable invite only to an owned test mailbox. Confirm original headers pass SPF, DKIM, DMARC, From/Reply-To, direct HTTPS action link, absence of tracking pixel and invalid unsubscribe headers.
3. Confirm scanners/repeated GETs leave the invite pending, then complete it in the owned test account.
4. Obtain the exact warning text, its location (Gmail/Chrome/managed device), warning hostname and failing email authentication results from an affected recipient. Redact live tokens from shared notes. Do not claim the recipient-specific issue is resolved without this evidence.
5. Monitor SendGrid deferred/blocked/bounce/complaint events and Google Postmaster Tools. Low-volume senders may have no Postmaster data; keep using the shared IP pool.
6. Request Google review only if Security Issues or a reproducible Safe Browsing false positive establishes a flag. Keep DMARC quarantine because observed legitimate mail passes; use p=none only for an explicitly needed diagnostic monitoring phase.
