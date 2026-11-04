# Support office consistency and routing review — 4 November 2026

## Scope

Review based on main `7b5da6b9b9dfe9778a6b9cd7a02e81a082441662` and Sam's browser handover. No production data was read directly or changed by this coding task. Historical browser figures below are supplied observations, not a fresh live verification.

Sam confirmed Singapore/Malaysia retain network announcements and direct messages without state hubs. Hide MinitR 0101, Rhett 01111, operator 3904 and the four named Mobile Services placeholders from the directory; retain real not-yet-invited shops.

## Findings and changes

1. Testing-mode JSON website enquiries used the production escalation/default selectors. With neither configured they returned 422/503 despite UI promising a Support office Inbox. Routing preview also depended on the escalation selector. Testing mode now resolves exactly one active linked HQ site, creates the website enquiry there, and adds an Inbox alert with a read-only enquiry viewer. No SMS, email, automatic job or cascade is created in this mode. Missing/ambiguous HQ fails explicitly. The production escalation/default behavior is unchanged; testing mode is never switched off by this work. BCC email capture is a separate existing intake path.
2. Navigation counted the first 50 captured emails while the Inbox fetched up to 500 using the same query key. A parent-scoped COUNT of all new emails now feeds the badge, with a distinct tenant-scoped cache key. The Inbox explains its loaded-list limits. Alerts and email enquiries remain separate counts; email receipt events are excluded from the alert portion to prevent double-counting.
3. Display and retail-target classification now share the six reviewed Minit van identities (2915, 4903, 6902, 6903, 8901, 8905). Stored roles are untouched. Dashboard counts, zero-booking retail rows, under-goal targeting and shop-message recipient validation use the same operational classification. Historical booking rows/totals and intentional mobile reporting visibility are preserved.
4. The seven reviewed test/placeholder records are hidden from Minit's directory and excluded from announcement receipt/alert audiences and retail targets. Existing conversations and memberships are not deleted. Rules are scoped to the named Minit parent; unrelated networks keep their existing behavior. The directory says linked sites, not participating/online shops, and retains real sites awaiting invitations.
5. The overseas warning mismatch is intentional filtering: `messaging_hubs.intentionally_excluded` omits Singapore/Malaysia/SEA from missing-state warnings. No overseas hubs or state assignments are added. Copy now explains AU/NZ hub coverage and the overseas DM/announcement policy. Multi-state Support office views avoid the single-shop hub headings.
6. A read-only territory review exposes current route targets, exact account IDs, route counts, states, example suburbs and readiness issues. It shows testing-mode status and the separate escalation configuration without returning passwords, webhook secrets or contact numbers. It never chooses a replacement, activates dispatch or writes routes.

## Territory ownership stays with Minit

Sam confirmed that Minit decides its operators' coverage. No route reassignments, replacement-account proposals or coverage changes are part of this work.

The browser handover observed 524 suburbs mapped to minit-mobile-6441 (Baldivis) and 275 to minit-mobile-2311 (Queanbeyan). The read-only screen reports current account identities and readiness for Minit's review. These figures do not authorize changes and are not a request for Sam to nominate replacements. Testing mode remains on.

## Browser verification after an approved deployment

1. Confirm the reviewed release is live. Read testing mode ON; do not save it off. Verify existing entitlement totals remain 383 parent-paid booking, 28 parent-paid mobile services and two complimentary Pro (413 total), or investigate any intervening authorized changes. No further blanket grant.
2. Read the territory review if useful to Minit; coverage decisions and route management remain with Minit. No operator activation, account retirement, ownership/link changes or van folds.
3. Verify the seven exclusions are absent from the directory, the six vans show as operators, and real awaiting-invitation shops remain visible. Overseas accounts should show no state hub while retaining DM/network announcement eligibility.
4. Compare badge counts against the new-email count plus Inbox alerts; remember the rendered lists are capped at 500 each. Verify enquiry detail is accessible only to the correct Support office.
5. Confirm retail under-goal lists and server-side shop-message validation omit the vans/exclusions. Preserve intentional mobile report rows and compare matching report periods, rather than treating all screens as the same account population.
6. Live message/intake delivery tests remain pending. First agree exact test participants, destinations and labelled content with Sam. Automated tests mock all outbound delivery. Do not submit real customer leads, send messages/announcements or trigger SMS/email as part of read-only verification.

Continue skipping 3904. Rouse Hill remains excluded from entitlement grants pending exact setup confirmation. Corporate 4903 is Support office's van and must never be folded into an ordinary shop. Chadstone's shop and operator remain separate. Automated billing stays off.
