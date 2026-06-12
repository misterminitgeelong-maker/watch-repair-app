# Release Notes

## Last Two Weeks Update (Mar 30 - Apr 8, 2026)

This release focused on three outcomes: a mobile-first field experience, significantly smarter auto-key workflows, and stronger platform reliability for daily operations.

### Highlights

- Mobile Services is now faster and cleaner on phones, with bottom-tab navigation and improved responsive layouts across core pages.
- Auto-key execution is smarter: AKL complexity indicators, known issue warnings, recommended tools, and cutting machine profile guidance are now surfaced in workflow context.
- Quote suggestions now support pricing tiers (retail, B2B, and tier levels) to improve consistency and margin control.
- Dispatch and scheduling usability improved through clearer week cards, direct call links, and better technician-facing context.
- Deployment reliability improved through Railway startup and boot-path fixes.
- PWA polish shipped: improved install prompts, icon updates, and cache/versioning updates.

## Customer-Facing Summary

### What changed for teams

- **Better mobile experience:** smoother navigation and less friction in field workflows.
- **Smarter auto-key jobs:** critical vehicle context appears inside job flows, reducing guesswork.
- **More consistent pricing:** quote suggestion tiers help align pricing by customer segment.
- **More reliable app behavior:** startup and deployment fixes reduce interruptions.

### Why it matters

- Faster job execution in the field
- Fewer avoidable diagnostics and programming mistakes
- More consistent quoting
- Better day-to-day confidence in app stability

## Internal Engineering Notes

### Delivery snapshot

- 84 commits over the period
- 94 files touched
- High-churn areas concentrated in:
  - `frontend/src/pages/AutoKeyJobsPage.tsx`
  - `frontend/src/lib/api.ts`
  - `backend/app/routes/auto_key_jobs.py`
  - `backend/app/routes/vehicle_key_specs.py`

### Major workstreams

- **Mobile-first UX pass**
  - Bottom tab bar navigation
  - Responsive layout pass across dashboard, jobs, quotes, invoices, and scheduler flows
  - Scheduler/map/job-card improvements for dispatch and in-field use

- **Auto-key intelligence expansion**
  - New API support for quote tiers and vehicle job context
  - UI integration for complexity badges, known issues, tool recommendations, and cutting profiles
  - Expanded and normalized seed datasets for vehicle specs and locksmith decision support

- **Platform hardening**
  - Railway startup fixes and deployment-path cleanup
  - Build/type cleanup passes to keep deploys green
  - PWA install/caching improvements

### Follow-up priorities

- Split `AutoKeyJobsPage` into smaller components/hooks to reduce regression risk.
- Add more contract tests for new auto-key endpoint behavior.
- Add CI checks for startup health and seed-data sanity.

