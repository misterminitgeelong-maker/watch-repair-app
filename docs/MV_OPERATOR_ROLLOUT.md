# MV operator consolidation

Apply migration `20260930a_mv_merge_safety` before deploying the updated API.
Existing operators retain their dispatch setting. Newly classified MVs are paused.
This change does not automatically modify production tenant roles or merge records.

## Review and apply

1. Rehearse on a recent restored production database. Verify the backup can be restored.
2. Pause ingestion, booking creation, imports and background dispatch for the affected
   shops; drain in-flight requests. Tenant row locks serialize merges, but they are
   not an application-wide write barrier. Keep affected writers paused through verification.
3. Open **Merge MV duplicates**. Review tenant identity, franchisee, contacts,
   proposed plan, route count and blockers. Directory shop phone and dispatch mobile
   are different fields. The UI never silently uses the former for dispatch.
4. Start with one unambiguous pair, then batches of at most five. Each pair commits
   separately. The preview fingerprint is checked again before execution. A changed
   preview must be refreshed; do not assume a previously selected pair still applies.
5. Confirm the operator's SMS number and ability to sign in before checking activation.
   Otherwise merge with dispatch paused and arrange HQ coverage. Historical snapshots
   remain on their original identities; current reports use the surviving MV operator.
6. Check current Mobile reports, suburb resolution, fallback ranking, owner access,
   dispatch delivery and billing reconciliation. Resume writers only after these checks.
7. Repeat an import in preview mode and verify the old placeholder is reported as
   `merged_operator`, not created or updated.

**Make operator only** changes classification, leaves plan/routes/contacts intact and
pauses new dispatch when converting a retail MV. Both identities remain in reports
until the duplicate is resolved. **Activate dispatch** is available for MVs without
a matching placeholder; it upgrades booking-only to Basic Auto Key and requires an
explicit dispatch number and access confirmation. It does not assign new territories.

Sources with prospects, customer/business records, booking/dispatch references,
unknown tenant-owned data or cross-network references are blocked. Kotara must be
reviewed separately; this release intentionally does not migrate invoices/payments
or implement a general tenant-to-tenant record mover. Unknown constraints fail the
pair rather than discarding source rows. Completed pairs remain committed if a later
pair or billing synchronization fails; inspect the per-pair results before retrying.

## Audit and recovery

The `mobile_van_merged` event's `details_json` stores source/destination IDs, exact
changed reference row IDs, tenant and site before/after values, removed memberships
and grants, and revoked invite IDs/statuses. It contains no credentials or invite tokens.
The source tenant remains present with `merged_into_tenant_id` and revoked access.

Before commit, failures roll back the pair. There is no one-click production undo.
For post-commit recovery, stop affected writers and use the event manifest to compare
every recorded after-value with current data. Restore only exact recorded rows/fields
when they still match. If new work, payments, routing changes or access changes exist,
prepare a reviewed compensating migration. Never globally replace the destination ID
with the source ID. Do not automatically revive authentication, grants or invites;
reissue access after review. Full database restore is disaster recovery, not per-pair undo.

## Validation limits

Phone syntax, an active user and an accepted owner invite are checked by the server; delivery and actual owner
access require HQ's confirmation. Existing legacy operators are not automatically
paused or cleaned up by the schema migration. A dispatch-paused MV is excluded from
new territory/fallback selection, shop booking options and targets, pool alerts and
pool claims. Classification still includes it in operator reports. Already-existing
work remains accessible to authorized users.
