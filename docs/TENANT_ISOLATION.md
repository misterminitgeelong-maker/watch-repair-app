# Tenant isolation

Mainspring is multi-tenant, and the tenants are competing shops in a franchise
network. One shop seeing another's customers or jobs is the highest-consequence
bug this system can have.

## How it works

A session can carry the tenant it is allowed to see. A SQLAlchemy
`do_orm_execute` listener (`app/tenant_scope.py`) then adds
`tenant_id = :tenant` to every ORM statement touching a table that has a
`tenant_id` column.

`get_auth_context` stamps the session with the caller's tenant. FastAPI caches
`get_session` per request, so the session it stamps is the same object the
endpoint receives — which is why every authenticated route is scoped without any
of them being edited.

The list of scoped tables is **derived from the model metadata**, not
hand-maintained. A new tenant-scoped table is protected the moment it exists. A
hand-written list would be the same "remember to add it" problem this exists to
remove.

## What it covers

Measured, not assumed:

| | |
|---|---|
| `select()` | scoped |
| `session.get(Model, id)` | scoped — this is the important one |
| Joins | scoped on every participating table |
| ORM bulk `UPDATE` / `DELETE` | blocked across tenants |

`session.get()` mattering is the reason this design was chosen over a
`get_owned()` helper: 327 lookups in `routes/` are primary-key gets, and they are
all covered without being touched — including the ones written next year.

## What it does not cover

- **Raw `text()` SQL.** Bypasses the ORM entirely.
- **Writing a new row with the wrong `tenant_id`.** A different bug: there is no
  existing row to filter. Setting `tenant_id` from `auth.tenant_id` rather than
  from request input remains the endpoint's job.
- **Tables with no `tenant_id`.** Nothing to scope by.

The existing manual `if row.tenant_id != auth.tenant_id` checks were **left in
place**. They are now belt and braces rather than the only thing standing
between tenants, and removing 325 of them would be a large diff whose only
effect is to remove a safety net.

## Crossing the boundary on purpose

Some endpoints genuinely span tenants. They take `unscoped_session` instead of
`get_session`:

| module | why |
|---|---|
| `auth` | resolves a user before a tenant is known |
| `billing` | Stripe webhooks carry a tenant id from the provider, not a token |
| `inbound_email` | routes mail to whichever shop in the network owns it |
| `parent_accounts` | parent-account membership across its shops |
| `parent_operations` | franchise-network reporting across shops |
| `platform_admin` | administration across all tenants |
| `shop_mobile_bookings` | dispatch between a requesting shop and an operator shop |
| `shop_owner_invites` | onboards a shop that is not the caller's tenant |

**Taking `unscoped_session` means the endpoint owns its own tenant checks.**
There is a test asserting that this list of modules matches exactly — adding a
module to it requires changing that test, which is the point. A reviewer audits
eight modules instead of 325 query sites.

For a narrow cross-tenant lookup inside an otherwise scoped request, use
`without_scope(session)` rather than opening a second session:

```python
with without_scope(session):
    rows = session.exec(select(ParentAccountMembership).where(...)).all()
```

Opening a separate session returns objects belonging to a different identity
map, and attaching them to the caller's session raises *"another instance with
key ... is already present"*. That was found the hard way; the context manager
exists so nobody finds it again. Keep the lifted block as small as the query.

## Why not Postgres row-level security

RLS is the stronger mechanism in principle and was rejected for this codebase
for three concrete reasons:

1. It needs a per-connection session variable. With a pooled connection, a
   leaked variable **is** a cross-tenant leak — the fix could create the bug.
2. Tests run on SQLite, which has no RLS. The primary safety mechanism would be
   invisible to the `backend-sqlite` job. Three bugs have already reached
   `main` in this project precisely because SQLite could not express the
   behaviour under test.
3. The eight cross-tenant modules and seven background sweeps would need a
   bypass role, moving the risk to "did we connect as the right role".

RLS remains available later as defence in depth, once the application layer is
already correct — at which point a session-variable mistake is caught by tests
rather than being the only thing between tenants.

## Tests

`backend/tests/test_tenant_scope_structural.py`. Every isolation assertion there
was verified to **fail** with the listener disabled, including the end-to-end one
that drives a deliberately careless endpoint over HTTP. A guard that cannot fail
is worse than no guard.
