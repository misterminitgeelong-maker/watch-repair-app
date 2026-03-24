# ServiceM8 vs Mainspring Mobile Services — Feature Comparison

ServiceM8 is a field service management platform (iOS-native, Android Lite) popular with Australian trades including locksmiths. This doc compares it to Mainspring's Mobile Services module to identify gaps and differentiators.

## Solo-operator focus

**Mainspring:** Optimised for solo operators (99% of mobile key/locksmith users). When there's only one user, we hide tech assignment, simplify the dispatch view (flat "Today's schedule" instead of grouped by tech), and skip the "Jobs by tech" report. Value line emphasises "Plan your day, track mobile vs shop work."

**ServiceM8:** Built for multi-tech operations with dispatch boards, tech assignment, and staff management. Heavier on team workflow.

---

## What ServiceM8 has that we don't (yet)

| Feature | ServiceM8 | Mainspring | Notes |
|---------|-----------|------------|-------|
| **Native mobile app** | iPhone/iPad native, Android Lite | Web-responsive only | We're web-first; native app later per plan |
| **Offline access** | Full offline: jobs, schedule, photos, signatures sync when back online | Online only | Significant for field techs in poor reception areas |
| **Dispatch map** | Live map of staff locations | — | GoFar integration explored for later |
| **Auto routing** | Optimise route order for the day | — | Not planned |
| **Drag-and-drop scheduling** | Drag jobs onto calendar | Week view with time slots; no drag | Possible enhancement |
| **SMS booking links** | Client picks time via link | — | Different use case (we have prospects) |
| **Signature capture** | On-site customer sign-off | — | Could add for quote approval or completion |
| **Time tracking** | Clock in/out of jobs, billable hours, timesheets | Work logs for watch jobs only | Mobile-specific time tracking not yet |
| **Tap to Pay / contactless** | On-site payment (iPhone) | Manual payment capture | Different payment flow |
| **Job reminders + travel time** | "Leave now" alerts with ETA | Day-before reminders | Partial |
| **Auto check-in** | GPS detects arrival | — | Not planned |
| **Barcode scanning** | Materials on invoice | — | Not planned |
| **Voice photo tagging** | Hands-free photo labels | — | Not planned |
| **Apple Watch** | Job info, messages, nav | — | Not planned |
| **Online booking** | Customer self-serve booking | Prospects module; different | — |
| **Accounting integrations** | Xero, QuickBooks, MYOB | — | Different stack |

---

## What we have that ServiceM8 doesn't emphasise (for locksmiths)

| Feature | Mainspring | Notes |
|---------|------------|-------|
| **Vehicle / rego lookup** | Blue Flag NEVDIS integration; auto-fill make, model, year, VIN from plate + state | Locksmith-specific; saves data entry |
| **Key-specific fields** | Key type, quantity, programming status | Tailored to key cutting/programming workflow |
| **Multi-vertical platform** | Watch + Shoe + Mobile Services in one product | Shops doing multiple repair types use one system |
| **B2B customer accounts** | Statement billing, monthly aggregation | Fleet/dealer accounts |
| **Quote approval flow** | Tokenised approve/decline links, audit trail | Customer can approve from link without login |
| **Solo-operator UX** | Tech assignment hidden when 1 user; flat schedule view | Fits sole traders better |

---

## Aligned features

| Feature | ServiceM8 | Mainspring |
|---------|-----------|------------|
| Job management | ✓ | ✓ |
| Scheduling (date/time) | ✓ | ✓ |
| Job type (mobile vs shop) | ✓ | ✓ |
| Job address + directions | ✓ Get directions → Maps | ✓ |
| Quotes & invoicing | ✓ | ✓ |
| Quoting on site | ✓ | ✓ |
| Photos on jobs | ✓ | ✓ |
| Day view / week calendar | ✓ | ✓ |
| Customer history | ✓ | ✓ |

---

## Suggested next steps (priority for solo mobile operators)

1. **Offline-capable PWA** — ✓ Service worker caches app shell; manifest for installability.
2. **Signature capture** — ✓ Optional customer signature on quote approval (ApprovePage).
3. **SMS time-window** — ✓ Send arrival SMS with time window (e.g. "Tech arriving 9–11am").
4. **Drag-and-drop scheduling** — ✓ Week view supports drag between slots; unscheduled bucket.

5. **Map view** — ✓ Map tab shows today's mobile jobs; geocoding via Nominatim.
6. **Route order** — ✓ `visit_order` field; jobs sorted by route order.

Live staff tracking, auto routing, and Tap to Pay remain lower priority for the solo locksmith segment.
