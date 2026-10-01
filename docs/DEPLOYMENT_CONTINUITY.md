# Deployments without signing users out

A restart does not invalidate the JWT signing key or the persisted refresh sessions.
The failures were in the browser's recovery paths: a refresh 401 recursively joined
its own promise; proactive refresh cleared credentials on network/5xx failures;
failed session loading never retried; missing lazy imports waited indefinitely while
forcing a reload; and the new image no longer contained the old hashed route files.

## Runtime contract

- Refresh uses a separate, bounded Axios request with one shared operation per tab.
  Only a refresh rejection (401/403) clears credentials. Network errors, timeouts,
  429 and 5xx retain the login. A late response cannot overwrite logout, login or
  a site switch, and an old account's request cannot retry under a new account.
- Session identity retries after transient errors with backoff capped at 30 seconds;
  online/focus retries sooner. Proactive refresh retries after a temporary outage.
  A session outage does not remount an already validated workspace or clear forms.
  Initial workspace failure shows reconnect/retry/sign-out controls instead of an
  unexplained spinner. Successful recovery restores the server's current permissions.
- Concurrent refresh token rotation is locked in Postgres. The existing reuse grace
  allows adjacent requests to use the just-replaced token. Revoked/expired sessions
  still reject normally; deployment resilience does not extend authentication expiry.
- Do not replay payments, invoices or other writes on connection/5xx errors: the
  response may have been lost after the write committed. Use an idempotency key
  before introducing write retries. The existing 401 retry only follows authentication
  rejection, before the protected handler has accepted the operation.

## Build and rollout

1. Build the complete image while the old deployment continues serving.
2. Run additive migrations, then `python -m app.frontend_assets --bootstrap-live`.
   Publish every current hashed asset to the existing private Supabase bucket under
   `_frontend-builds/v1/`. A filename cannot overwrite different content.
3. On the first rollout, traverse the live index and same-origin hashed JS/CSS
   dependencies to preserve its lazy pages too. Mark the archive complete only after
   every file succeeds. Subsequent rollouts skip a complete unchanged live archive.
   Four workers limit pre-deploy latency. Failure aborts rollout before traffic switches.
4. Wait for `/v1/ready` (actual DB connectivity), with a 300-second startup allowance.
5. Railway overlaps the old deployment for 60 seconds and drains it for 120 seconds;
   Uvicorn has a matching graceful shutdown allowance. The app service currently has
   no mounted volume; the separate Postgres service has its own volume.
6. Open tabs keep their immutable build files. `/assets/` serves current local files,
   then older archived files, caching downloads locally. Only flat eight-character
   Vite hash filenames and build extensions are eligible; attachments and arbitrary
   storage keys are not exposed. Credentials remain server-side and the bucket private.
7. The worker migrates cached bundles out of older shell caches before deleting them,
   uses a persistent cache for immutable hashes, and never caches API data. New versions
   remain optional; neither missing imports nor the version banner force reload.

Build files are deliberately retained across releases. Monitor `_frontend-builds/v1/`
storage growth; do not delete old files without first defining a supported tab lifetime
and an explicit update policy. Renaming this prefix or changing the asset hash format
also needs a compatibility migration.

## Rules for future changes

Both server versions and old browser builds can be active together. Database changes
must use expand/backfill/contract: add nullable columns or compatible defaults first,
backfill separately, and only remove old columns/fields once all supported callers have
migrated. Keep old API paths and payload fields valid during that window. Do not rotate
JWT_SECRET or revoke sessions as part of a routine deployment. Never attach a persistent
volume to the web service without revisiting Railway's deployment overlap limitation.

Railway currently documents legacy config-as-code support until 2026-12-01. Migrate
this existing service to Infrastructure as Code before that date while preserving these
readiness, overlap, draining and pre-deploy settings. Do not change live infrastructure
as part of the daytime preparation.

Push to main only after 18:00 Australia/Sydney, as requested by the platform owner.

## Verification (2026-10-01)

- Full frontend suite: 382 tests passing, including refresh rejection, single operation,
  temporary outage recovery, late logout/login responses, non-replayed writes and worker
  cache migration. Backend auth and build-retention suite: 43 tests passing on SQLite.
  A concurrent PostgreSQL-only regression test is included; it is skipped locally and
  still requires verification in the Postgres CI environment.
- Read-only traversal of the current live build: 196 assets, approximately 2.4 MB. The
  existing Supabase `attachments` bucket is private with no MIME or file-size restriction.
- Live local browser: one-minute JWTs, server stopped with an unsaved POS description
  and price, server restarted; refresh returned 200, session returned 200 and the same
  POS fields remained. No logout or page reload was used.
- Production overlap, archived-file downloads and an already-open live tab must be
  verified during the first permitted rollout after 18:00. An already hung old tab
  cannot receive new JavaScript recovery code until that tab reloads once. The compiled
  POS test also retained its unsaved $123 entry through nearly an hour of one-minute
  token refreshes after restart.

References: https://docs.railway.com/deployments/healthchecks,
https://docs.railway.com/deployments/deployment-teardown,
https://docs.railway.com/config-as-code/reference,
https://vite.dev/guide/troubleshooting.
