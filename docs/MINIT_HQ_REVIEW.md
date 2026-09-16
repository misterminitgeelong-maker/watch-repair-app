# Minit HQ — cold review of the parent-account model

Fresh-eyes review of the HQ surface: the nine pages under `/minit/*`, the two
route modules behind them (`parent_operations.py`, `parent_accounts.py`), and the
data model they rest on.

Everything below was **measured against a running Postgres with seeded networks
of 20, 100 and 300 shops**, not read off the code. Where I expected a problem and
found none, that is stated too — three of my initial hypotheses were wrong, and
the disproofs are as useful as the findings.

---

## What is genuinely good

Worth saying first, because it shapes what is worth changing.

**The dashboard does not N+1.** Query counts are *flat* from 20 to 300 shops:

| endpoint | queries | 20 shops | 100 shops | 300 shops |
|---|---|---|---|---|
| `operations/overview` | 25 | 61 ms | 60 ms | 71 ms |
| `operations/bookings` | 4 | 11 ms | 11 ms | 11 ms |
| `operations/mobile-jobs` | 6 | 14 ms | 16 ms | 22 ms |
| `operations/troubleshooting` | 12 | 15 ms | 18 ms | 23 ms |

Region stats, booking counts and status rollups are all done with `GROUP BY` in
SQL rather than per-shop loops. This is the part most franchise dashboards get
wrong, and it is right here. **Do not "optimise" it** — 25 queries is a lot to
read but it is constant, and the wall time is dominated by fixed overhead.

**Minit shops cannot escape their plan.** I tried to reach parent-account
endpoints as a shop owner by upgrading a `minit-*` tenant to `pro`.
`target_plan_for_minit_tenant` coerced it straight back to `booking_only`, and
the request stayed 403. That is a deliberate, working defence.

**Unlinking is properly guarded** — cannot unlink the active site, cannot unlink
the last one, and it unlinks rather than destroys.

---

## Findings, by consequence

### 1. HQ loses a shop the moment that shop takes its own login

**This is the big one.** Provisioned shops start out sharing the HQ owner's
credentials. `complete_shop_owner_invite` then does:

```python
owner.email = email
```

It **rewrites the existing shared user row** rather than creating a new one.
Measured consequence:

```
HQ site options before:                 23
minit-7003 owner email now:             'independent-shop@example.com'
is minit-7003 still in HQ's site list?  False
```

So the invite flow — whose whole purpose is to hand a shop its own login — is
also what removes HQ's visibility into that shop. And there is no other way in:
`enter_shop` is gated on `require_platform_admin`, which HQ users are not (they
are `role="owner"` of the HQ tenant).

**The net effect: the more successfully you onboard shops, the less of the
network HQ can actually see.** For "the full functioning parent account", that
is backwards.

**Fix:** give the parent account a first-class support route into its own shops —
an HQ equivalent of `enter_shop`, scoped to tenants linked to that parent, and
written to the tenant event log the way `platform_admin_enter_shop` already is.
The authorisation question is already answered by the membership table; it just
is not used for this.

### 2. A tenant can belong to more than one parent account, and resolution picks one arbitrarily

`parentaccountmembership` has a primary key on `id` and three plain indexes.
**No unique constraint at all.** Demonstrated by inserting directly:

```
memberships before:    24
memberships after:     26      (duplicate row + second parent both accepted)
tenants in >1 parent:   1
```

It also happens without anyone doing anything odd. Bootstrap auto-creates a
`ParentAccount` per `pro` owner, so in a generic multi-site setup both tenants
ended up in two parents:

```
 Generic Group | hq-generic
 Owner Group   | hq-generic
 Generic Group | shop-generic
 Owner Group   | shop-generic
```

And `_get_parent_account_for_user` resolves with:

```python
select(ParentAccount).where(ParentAccount.owner_email == user.email)
# .first() — no order_by
```

**Which parent account a user belongs to is therefore at the database's
discretion**, and can change between restarts or after a vacuum.

**Fix:** `UniqueConstraint("tenant_id")` if a shop may only ever have one parent
(true for a franchise), or `UniqueConstraint("parent_account_id", "tenant_id")`
plus a deliberate tie-break if not. Add `order_by(ParentAccount.created_at)` to
every resolution either way — a non-deterministic answer to "whose network am I
in" is not acceptable regardless of the constraint.

### 3. The parent account is identified by an email string

`ParentAccount.owner_email` is the primary link, matched by string equality in
both `_get_parent_account_for_user` and `_build_available_sites_for_email`.

Consequences:

- **Only one human can be HQ.** There is no way to have an HQ operations manager
  and an HQ finance controller with different access.
- Changing that email in the user table silently moves the whole account.
- The HQ tenant slug is hard-coded (`MINIT_HQ_SLUG = "mmsupport"`), so product
  identity is a magic string rather than an attribute.

**Fix:** make HQ membership a role on `ParentAccountMembership` — `hq_admin`,
`hq_viewer`, `shop` — and resolve by membership rather than by email. That single
change unlocks multiple HQ staff, read-only regional managers, and revocation
without touching anyone's email.

### 4. Membership conflates org structure with user access

The table is `(parent_account_id, tenant_id, user_id)`. It is trying to be two
things: *which shops are in this network* and *which users can reach them*.

A shop with two users needs two rows for the same tenant, and
`linked_tenant_ids_for_parent` papers over it with `dict.fromkeys`. Grouping,
counting or joining on this table means remembering to dedupe every time.

**Fix:** split it. `ParentAccountSite(parent_account_id, tenant_id)` with a unique
constraint is the org chart; `ParentAccountUser(parent_account_id, user_id, role)`
is the access list. Both become cheap to query correctly and impossible to
duplicate.

### 5. A shop's role in the network is inferred from its billing plan

```python
def _is_retail_shop(plan_code): ...   # "shop_mobile_booking" in PLAN_FEATURES[plan]
def _is_operator(plan_code):  ...     # plan in BOOKABLE_OPERATOR_PLAN_CODES
```

Retail shop versus mobile operator — the central distinction on the whole
dashboard — is derived from what the tenant is *billed for*. Change a shop's
plan for a commercial reason and its position in the network silently changes:
it moves between counts, drops out of region stats, and stops being offered
leads.

**Fix:** put `network_role` on the site record and let billing be billing. The
plan can still *default* it at provisioning time.

### 6. Region and area are free text with no lookup

`Tenant.minit_area` (120 chars) and `Tenant.minit_region` (40 chars) are plain
nullable strings, and `_region_dashboard_stats` groups by `minit_region`
directly. Nothing normalises them, so `"VIC SOUTH"`, `"VIC South"` and
`"Vic South"` are three regions on the dashboard. `minit_area` is not even
indexed.

There is also nowhere to hang the things a franchise network actually wants:
a regional manager, a target, a contact, an escalation path.

**Fix:** a `Region` table keyed by the parent account, with tenants referencing
it. That is what turns "group by a string" into "the regional manager for VIC can
see their own shops", which is the obvious next capability for this product.

---

## Hypotheses I tested and disproved

Recorded so nobody re-investigates them.

- **"A linked shop owner can read the parent account."** No. Minit shops are
  `booking_only`, which lacks `multi_site`, and the router gates on that feature.
- **"Upgrading a shop's plan escapes that gate."** No —
  `target_plan_for_minit_tenant` coerces `minit-*` tenants off disallowed plans.
- **"The HQ dashboard N+1s across shops."** No. Flat query counts from 20 to 300
  shops, measured.

---

## What I would do, in order

1. **HQ support access into linked shops** (finding 1). Without it, HQ's
   usefulness decays as onboarding succeeds. Everything else is tidying by
   comparison.
2. **Unique constraint + ordered resolution** (finding 2). Small, and it closes
   a correctness hole that is already live in the data.
3. **Roles on membership** (findings 3 and 4). This is the change that makes HQ
   a real organisation rather than one email address.
4. **Explicit `network_role`** (finding 5) and **a `Region` table** (finding 6),
   when regional reporting is next touched.

None of this is urgent in the sense of being broken today. The dashboard is
fast, the isolation holds, and the plan coercion works. The model is what will
limit what HQ can become — multiple staff, regional hierarchy, and supporting a
shop that has its own login are all blocked by the same few decisions.
