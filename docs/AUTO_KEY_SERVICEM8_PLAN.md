# Auto Key — ServiceM8-Style Build Plan

> **See also:** [ServiceM8 vs Mainspring feature comparison](SERVICEM8_COMPARISON.md) for a detailed gap analysis and solo-operator focus.

## Product decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Calendar view | **Week first** (then month) |
| Mobile | **Web-responsive for now**; native app later |
| Live tech tracking | **Later phase**; explore GoFar integration |
| Rego lookup | **Include** — auto-fill vehicle details from plate |

---

## Phase 1: Scheduling & dispatch ✓ (done)

- [x] Scheduled date
- [x] Job type (shop / mobile)
- [x] Job address
- [x] Dispatch tab with day view
- [x] Unscheduled queue

### Next small additions
- [x] Edit scheduled date/time on job detail
- [x] Scheduled time (not just date)

---

## Phase 2: Tech assignment & dispatch board ✓

- [x] Tech assignment visible on job cards and dispatch
- [x] Dispatch grouped by tech (columns per person)
- [x] Quick-assign tech from card or dispatch
- [x] Filter jobs by assigned tech

---

## Phase 3: Rego search / vehicle lookup ✓

**Goal:** Enter rego plate (+ state) and auto-fill make, model, year, VIN.

### Australian API options

| Provider | Type | Cost | Data | Notes |
|----------|------|------|------|------|
| **Car Registration API** | SOAP/XML | ~AUD $0.30/lookup | Make, Model, VIN, Insurer, 20+ fields | Free trial (10 lookups), min 100 block |
| **Blue Flag (NEVDIS)** | REST | Pay-per-request | VIN, make, model, colour, body_type, engine_number, state | `plate` + `state` params; NEVDIS data |
| **MotorWeb** | REST | Contact | NEVDIS access, VIN, specs | Brokers NEVDIS data |

**Suggested:** Blue Flag or Car Registration API — REST preferred if Blue Flag pricing fits.

### Implementation outline
1. Add env config: `REGO_LOOKUP_API_KEY`, `REGO_LOOKUP_PROVIDER` (blueflag | carregistration)
2. Backend: `POST /v1/vehicle-lookup` or `GET /v1/vehicle-lookup?plate=X&state=VIC`
3. Frontend: "Look up" button next to registration field; fills make, model, year, VIN on success
4. State selector: VIC, NSW, QLD, etc. (required for lookup)
5. Fallback: Manual entry if lookup fails or is disabled

---

## Phase 4: Week calendar view ✓

- [x] Week view (7 days)
- [x] Time slots (store date + time)
- [x] Jobs shown in time slots per day
- [x] Optional drag-and-drop scheduling (week view)

---

## Phase 5: Mobile-specific workflow ✓

- [x] Mobile status flow: `scheduled → en_route → on_site → completed`
- [x] "Get directions" → open Maps with job address
- [x] Mobile-optimised layout (touch targets ≥44px, touch-manipulation)

---

## Phase 6: Notifications ✓

- [x] Notify tech on schedule change
- [x] Optional day-before reminder (techs + customers)
- [x] Optional customer SMS ("Tech arriving 9–11") — Send arrival SMS on job detail
- Reuse Twilio if already integrated

---

## Phase 7: Maps & routes (later)

- [x] Map view of today’s mobile jobs (Mobile Services → Map; default **Mobile visits** filter)
- [x] Route order / optimisation (**By time**, **Optimized** straight-line nearest-neighbor, **Driving** via Google Directions with fixed first/last appointment; polyline + Open in Google Maps)
- [ ] Tech live location (GoFar integration)

---

## Phase 8: Reporting

- [ ] Jobs per tech
- [ ] Revenue by tech
- [ ] Mobile vs shop split

---

## Suggested execution order

1. **Phase 2** — Tech assignment (uses existing `assigned_user_id`)
2. **Phase 1.1** — Edit scheduled date/time on job detail
3. **Phase 3** — Rego search (high impact for data entry)
4. **Phase 4** — Week calendar view
5. **Phase 5** — Mobile status flow
6. **Phase 6** — Notifications

---

## Technical notes

- **Models:** `assigned_user_id`, `scheduled_at`, `job_address`, `job_type`, `registration_plate`, `vin`, `vehicle_make`, `vehicle_model`, `vehicle_year` exist
- **Rego API:** Use backend proxy (never expose keys to frontend)
- **GoFar:** Research integration for live vehicle/tech location later
