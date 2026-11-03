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
- Corrected the Google Workspace DKIM hostname from google._domainkey._domainkey.mainspring.au to google._domainkey.mainspring.au, retaining the exact key confirmed in Google Admin. Authoritative DNS resolves the key and Google Admin reports Authenticating email with DKIM. This is separate from SendGrid signing.
- Search Console domain property mainspring.au is verified under admin@mainspring.au and Security Issues reports No issues detected.
- Google Postmaster Tools domain mainspring.au is registered and successfully verified under admin@mainspring.au using the existing verification TXT. Manage Domains shows Verified and No issues. Actual dashboard history may remain empty at low sending volumes.
- Deployment follow-up is active in this chat for 18:05 Sydney time. Draft PR: https://github.com/misterminitgeelong-maker/watch-repair-app/pull/44.

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

## Junk-folder checklist (3 November 2026)

Code (this change): default sender is now admin@mainspring.au (a real, replyable mailbox on the authenticated root domain) instead of noreply@; tracking, mailing-list headers and fake unsubscribe headers are already removed. If Railway still has EMAIL_FROM_ADDRESS=noreply@em695.mainspring.au, change it to admin@mainspring.au and set EMAIL_REPLY_TO_ADDRESS=admin@mainspring.au (variable changes redeploy the app).

DNS / vendor steps for the owner (nothing here can be done from code):
1. SendGrid > Settings > Sender Authentication: confirm the domain mainspring.au shows Verified, and that the link-branding and bounce CNAMEs are present. Delete any stale em695 records only after confirming the live bounce CNAME (em2336).
2. Root SPF must stay a single TXT record. Only add include:sendgrid.net if mail is sent with a mainspring.au envelope; with the custom Return-Path it is not needed. Never publish two SPF records.
3. DMARC: keep p=quarantine while reports are clean. Add a rua mailbox you actually read (the current onsecureserver.net address is a registrar default). Once reports show only passing mail, move to p=reject.
4. Send a test to mail-tester.com and a Gmail account; check Show original for SPF/DKIM/DMARC = PASS and aligned.
5. For a Minit shop that sends from its own address, that address must not be used as From (SendGrid will reject or fail DMARC); it is used only as Reply-To, which is already the case.
6. Warm-up: volume is low and new, so the first weeks can land in junk regardless. Ask recipients to mark Not junk and add admin@mainspring.au to contacts, especially Minit shop owners receiving invites.
