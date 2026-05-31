# Attachment Storage

Attachments (intake photos, signature PNGs, uploaded files) are written through
the `AttachmentStorage` abstraction in
[`backend/app/services/attachment_storage.py`](../backend/app/services/attachment_storage.py).
Two backends are implemented:

- **`LocalAttachmentStorage`** — writes to a filesystem directory
  (`ATTACHMENT_LOCAL_UPLOAD_DIR`, default `uploads/`).
- **`SupabaseAttachmentStorage`** — object storage (Supabase Storage bucket), with
  signed download URLs.

The active backend is chosen by `create_attachment_storage()` based on
`ATTACHMENT_STORAGE_BACKEND`:

| Value | Behaviour |
|-------|-----------|
| `auto` (default) | Object storage when `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are set, otherwise local FS. |
| `local` | Always local filesystem. |
| `supabase` | Always object storage; **fails fast at startup** if Supabase is not configured. |

## Why object storage is preferred in production

Local filesystem storage only survives on a **single** instance with a durable,
mounted volume. As soon as the app scales horizontally (multiple instances behind
a load balancer) or runs on ephemeral disks (most PaaS), local files are not shared
and are lost on redeploy. Object storage (Supabase) is the recommended default for
any multi-instance or production deployment.

To enforce object storage in production set:

```
ATTACHMENT_STORAGE_BACKEND=supabase
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_STORAGE_BUCKET=attachments
```

## Migration runbook: local FS -> Supabase object storage

1. **Provision** a Supabase Storage bucket (e.g. `attachments`), private (signed
   URLs only). Capture `SUPABASE_URL` and the **service role** key.
2. **Stage config** with `ATTACHMENT_STORAGE_BACKEND=auto` (or unset) so the app
   keeps reading existing local files while you copy them up.
3. **Copy existing files**: upload the contents of `ATTACHMENT_LOCAL_UPLOAD_DIR`
   to the bucket, preserving the relative path of each file as its storage key
   (the DB stores the same `storage_key` for both backends, so keys must match
   exactly). Verify a sample with a signed-URL download.
4. **Cut over**: set `ATTACHMENT_STORAGE_BACKEND=supabase` and redeploy. New
   uploads now go to object storage; reads use signed URLs.
5. **Verify** upload + download for a same-tenant user and confirm a cross-tenant
   download is still rejected (tenant isolation is enforced in the route layer,
   not the storage layer).
6. **Decommission** the local volume only after a verification window and a backup.

Rollback: set `ATTACHMENT_STORAGE_BACKEND=local` and redeploy (only valid while the
local files still exist and the volume is attached).

## Retention and cleanup policy

- **Orphan definition**: a stored object whose `storage_key` is no longer
  referenced by any `Attachment` (or signature key on a quote/job) row.
- **Cause**: rows can be deleted (job/quote/attachment removal) without deleting
  the underlying object, leaving orphaned blobs.
- **Policy**:
  - Retain attachments for the life of the parent job/quote plus the business
    record-retention window (set per deployment; e.g. 7 years for financial
    records in AU).
  - Run a periodic (e.g. weekly) reconciliation job that lists stored keys, diffs
    against referenced `storage_key`s in the DB, and deletes objects that have
    been orphaned for longer than a safety grace period (e.g. 30 days).
  - Always operate the cleanup against object storage with a dry-run first
    (log the keys it would delete) before enabling deletion.
- **Backups**: object storage bucket should have versioning/backup enabled so an
  accidental delete is recoverable within the grace period.

> The reconciliation/cleanup job is not yet implemented in code; this section
> defines the policy and the contract (`storage_key` is the single source of
> truth shared by DB rows and stored objects) that an implementation must follow.
