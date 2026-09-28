# Platform admin walkthrough and redesign

Reviewed 28 September 2026. The live account was inspected read-only across Shops, Billing, Audit log, Users, and Reports. Account edits, impersonation, payments, suspensions, and deletion were not executed against live shops.

## Findings and changes

| Area | Walkthrough finding | Implemented change |
| --- | --- | --- |
| Entry point | The console opened directly into a long shop list, without a platform summary. | A new Overview landing page shows account totals, billing follow-ups, recent shops, plan distribution, and 30-day operations. |
| Shops | 459 accounts in one list, with repeated account actions on every row. | 25-row pagination, status and plan filters, alphabetical/newest sorting, readable plan names, and compact Enter Shop / Manage controls. Exact slug searches isolate the intended account. |
| Mobile management | Change Plan and Mark Paid were absent from the mobile shop cards. | A shared management dialog exposes the same actions on desktop and mobile, with larger touch targets. |
| Billing | Follow-ups required navigating away and manually searching for the shop. | Shop names link to the filtered directory; billing results are paginated. |
| Users | An unpaginated directory; failed requests could appear to be an empty list. | Role filtering, pagination, and an explicit error/retry state. |
| Audit | Filters and CSV exports apply only to fetched pages, which was not obvious. | The screen states how many events are loaded and matched; export is labelled “Export loaded results.” |
| Reports | “Healthy shops” displayed the active-account count despite separate activity health. | The metric is labelled “Active accounts”; actual healthy/attention counts use each shop’s health status. Added service distribution bars, shop search, health filtering, and pagination. Invoice totals are identified as shop invoicing. |
| Controls | Cancelling the optional reason prompt could still suspend/reactivate an account or force logout. | Cancellation now aborts those mutations. Existing typed confirmations remain. Edit and plan forms use the shared accessible modal with focus handling and Escape dismissal. |
| Navigation | Generic repeated heading text and no manual refresh. | Distinct section descriptions, an Overview sidebar link, accessible section navigation, and refresh for platform queries. |

## Validation and boundaries

- Production frontend build and TypeScript checks.
- Focused console interaction tests for overview links, pagination/filtering, linked searches, dialog actions, cancellation, and failed user loading.
- Focused ESLint checks on changed admin components and tests.
- Browser inspection of the real components with synthetic preview data at desktop and phone widths, including overview, reports, shop search, and mobile management.
- The overview screenshot in `artifacts/platform-admin/overview.png` uses sample data.

Changes are local and have not been deployed. The live Users screen stayed in its loading state during inspection; its successful data load could not be verified. The new directory was checked with sample data, and its failure handling was tested, but the live loading issue is not diagnosed. Live write operations and an authenticated integration walkthrough of the redesigned build still require a staging/deployed environment. Audit filtering remains limited to loaded events; no new backend filtering endpoint was introduced.
