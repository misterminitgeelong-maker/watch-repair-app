/** Versioned, scoped intake draft storage.

Intake forms on a phone are easy to lose: the browser backgrounds the tab, the
user taps a link, or the OS reclaims memory. Drafts are written to localStorage
under a versioned envelope so a stale or incompatible payload can never break a
form — an envelope that fails validation is dropped, not restored.

Only JSON-serialisable values are stored. File/Blob objects are stripped by
`sanitizeDraftValue`; callers keep photo metadata (name/size/count) and tell the
user photos must be reselected.
*/

/** Bump when a stored draft shape changes incompatibly — old drafts are dropped. */
export const DRAFT_SCHEMA_VERSION = 1

/** Drafts older than this are treated as abandoned. */
export const DRAFT_TTL_MS = 12 * 60 * 60 * 1000

const KEY_PREFIX = 'mainspring.draft'

export type DraftEnvelope<T> = {
  /** Envelope schema version. */
  v: number
  /** Intake kind, e.g. `watch-intake`. */
  kind: string
  /** Shop/user scope the draft belongs to. */
  scope: string
  /** Epoch ms the draft was written. */
  savedAt: number
  data: T
}

export type LoadedDraft<T> = {
  data: T
  savedAt: number
}

/** Stable per-shop/per-user scope so one device never restores another login's draft. */
export function draftScope(tenantId?: string | null, userId?: string | null): string {
  return `${tenantId || 'no-tenant'}:${userId || 'no-user'}`
}

export function draftStorageKey(kind: string, scope: string): string {
  return `${KEY_PREFIX}.v${DRAFT_SCHEMA_VERSION}.${kind}.${scope}`
}

function storage(): Storage | null {
  try {
    if (typeof localStorage === 'undefined') return null
    return localStorage
  } catch {
    return null
  }
}

/** Photo metadata kept in a draft — never the File itself. */
export type DraftPhotoMeta = {
  name: string
  size: number
}

export function photoMetaFromFile(file: File): DraftPhotoMeta {
  return { name: file.name, size: file.size }
}

const NON_SERIALISABLE = ['File', 'Blob', 'FileList', 'ArrayBuffer', 'FormData']

function isNonSerialisableObject(value: object): boolean {
  const name = value.constructor?.name
  if (name && NON_SERIALISABLE.includes(name)) return true
  // jsdom/older browsers may not name the constructor; duck-type File/Blob.
  const maybeBlob = value as { size?: unknown; type?: unknown; arrayBuffer?: unknown }
  return typeof maybeBlob.arrayBuffer === 'function' && typeof maybeBlob.size === 'number'
}

/**
 * Deep-copy `value`, dropping anything that cannot survive JSON round-tripping
 * (File/Blob, functions, symbols, undefined). Returns `undefined` when the whole
 * value is unstorable so callers can omit the key entirely.
 */
export function sanitizeDraftValue<T>(value: T): unknown {
  if (value === null) return null
  const type = typeof value
  if (type === 'string' || type === 'boolean') return value
  if (type === 'number') return Number.isFinite(value as number) ? value : undefined
  if (type !== 'object') return undefined
  if (value instanceof Date) return (value as Date).toISOString()
  if (isNonSerialisableObject(value as object)) return undefined
  if (Array.isArray(value)) {
    return value.map(item => {
      const clean = sanitizeDraftValue(item)
      return clean === undefined ? null : clean
    })
  }
  const out: Record<string, unknown> = {}
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    const clean = sanitizeDraftValue(item)
    if (clean !== undefined) out[key] = clean
  }
  return out
}

/** Write a draft. Returns false when storage is unavailable or full. */
export function saveDraft<T>(kind: string, scope: string, data: T, now = Date.now()): boolean {
  const store = storage()
  if (!store) return false
  const clean = sanitizeDraftValue(data)
  if (clean === undefined) return false
  const envelope: DraftEnvelope<unknown> = {
    v: DRAFT_SCHEMA_VERSION,
    kind,
    scope,
    savedAt: now,
    data: clean,
  }
  try {
    store.setItem(draftStorageKey(kind, scope), JSON.stringify(envelope))
    return true
  } catch {
    // Quota exceeded or private mode — drop the oldest drafts and try once more.
    try {
      clearExpiredDrafts(now)
      store.setItem(draftStorageKey(kind, scope), JSON.stringify(envelope))
      return true
    } catch {
      return false
    }
  }
}

function parseEnvelope(raw: string | null): DraftEnvelope<unknown> | null {
  if (!raw) return null
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return null
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
  const env = parsed as Partial<DraftEnvelope<unknown>>
  if (env.v !== DRAFT_SCHEMA_VERSION) return null
  if (typeof env.kind !== 'string' || typeof env.scope !== 'string') return null
  if (typeof env.savedAt !== 'number' || !Number.isFinite(env.savedAt)) return null
  if (env.data === undefined || env.data === null) return null
  return env as DraftEnvelope<unknown>
}

/** Read a draft, dropping it when it is stale, foreign, or an incompatible version. */
export function loadDraft<T>(
  kind: string,
  scope: string,
  opts: { now?: number; ttlMs?: number } = {},
): LoadedDraft<T> | null {
  const store = storage()
  if (!store) return null
  const now = opts.now ?? Date.now()
  const ttlMs = opts.ttlMs ?? DRAFT_TTL_MS
  const key = draftStorageKey(kind, scope)
  let raw: string | null = null
  try {
    raw = store.getItem(key)
  } catch {
    return null
  }
  const env = parseEnvelope(raw)
  if (!env) {
    if (raw != null) clearDraft(kind, scope)
    return null
  }
  if (env.kind !== kind || env.scope !== scope) {
    clearDraft(kind, scope)
    return null
  }
  // Clock skew (savedAt in the future) is treated as "just now", not as stale.
  if (now - env.savedAt > ttlMs) {
    clearDraft(kind, scope)
    return null
  }
  return { data: env.data as T, savedAt: env.savedAt }
}

export function clearDraft(kind: string, scope: string): void {
  const store = storage()
  if (!store) return
  try {
    store.removeItem(draftStorageKey(kind, scope))
  } catch {
    /* ignore */
  }
}

/**
 * Sweep drafts that are expired or written by an older schema version.
 * Returns the number of keys removed.
 */
export function clearExpiredDrafts(now = Date.now(), ttlMs = DRAFT_TTL_MS): number {
  const store = storage()
  if (!store) return 0
  const doomed: string[] = []
  try {
    for (let i = 0; i < store.length; i += 1) {
      const key = store.key(i)
      if (!key || !key.startsWith(`${KEY_PREFIX}.`)) continue
      if (!key.startsWith(`${KEY_PREFIX}.v${DRAFT_SCHEMA_VERSION}.`)) {
        doomed.push(key)
        continue
      }
      const env = parseEnvelope(store.getItem(key))
      if (!env || now - env.savedAt > ttlMs) doomed.push(key)
    }
    for (const key of doomed) store.removeItem(key)
  } catch {
    /* ignore */
  }
  return doomed.length
}

/** "just now" / "12 minutes ago" — used in the restore notice. */
export function describeDraftAge(savedAt: number, now = Date.now()): string {
  const diff = Math.max(0, now - savedAt)
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes === 1) return '1 minute ago'
  if (minutes < 60) return `${minutes} minutes ago`
  const hours = Math.floor(minutes / 60)
  if (hours === 1) return '1 hour ago'
  return `${hours} hours ago`
}
