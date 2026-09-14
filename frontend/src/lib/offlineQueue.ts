/** Minimal offline mutation queue (IndexedDB) for field techs.

Items are bound to the user who queued them, carry an idempotency key, and
move to a dead-letter store after repeated permanent failures so they cannot
block the rest of the queue.
*/

function readStoredAccessToken(): string | null {
  try {
    return localStorage.getItem('token') ?? sessionStorage.getItem('token')
  } catch {
    return null
  }
}

const DB_NAME = 'mainspring-offline'
const DB_VERSION = 2
const STORE = 'queue'
const DEAD_STORE = 'dead'
export const OFFLINE_QUEUE_MAX_ATTEMPTS = 5

export type OfflineQueueItem = {
  id: string
  method: string
  url: string
  body: string | null
  createdAt: string
  userId: string | null
  idempotencyKey: string
  attemptCount: number
  expectedUpdatedAt?: string | null
  lastError?: string | null
}

export type DeadLetterItem = OfflineQueueItem & {
  deadAt: string
  reason: string
}

type MemoryStores = {
  queue: Map<string, OfflineQueueItem>
  dead: Map<string, DeadLetterItem>
}

const memory: MemoryStores = {
  queue: new Map(),
  dead: new Map(),
}

function memoryFallback(): boolean {
  return typeof indexedDB === 'undefined'
}

export function userIdFromAccessToken(token: string | null): string | null {
  if (!token) return null
  const parts = token.split('.')
  if (parts.length < 2) return null
  try {
    const padded = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const pad = padded.length % 4 === 0 ? '' : '='.repeat(4 - (padded.length % 4))
    const json = atob(padded + pad)
    const payload = JSON.parse(json) as { user_id?: unknown; sub?: unknown }
    if (typeof payload.user_id === 'string' && payload.user_id) return payload.user_id
    if (typeof payload.sub === 'string' && payload.sub) return payload.sub
    return null
  } catch {
    return null
  }
}

export function currentQueueUserId(): string | null {
  return userIdFromAccessToken(readStoredAccessToken())
}

export function isPermanentSyncFailure(status: number | undefined): boolean {
  if (status == null) return false
  return status >= 400 && status < 500 && status !== 401 && status !== 409
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id' })
      }
      if (!db.objectStoreNames.contains(DEAD_STORE)) {
        db.createObjectStore(DEAD_STORE, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function runStore<T>(
  db: IDBDatabase,
  storeName: string,
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest<T> | void,
): Promise<T | void> {
  return new Promise<T | void>((resolve, reject) => {
    const tx = db.transaction(storeName, mode)
    const store = tx.objectStore(storeName)
    const req = run(store)
    if (req) {
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    } else {
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    }
  })
}

async function withStore<T>(
  storeName: string,
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest<T> | void,
): Promise<T | void> {
  const db = await openDb()
  try {
    return await runStore(db, storeName, mode, run)
  } finally {
    db.close()
  }
}

type QueueMutations = {
  deleteQueued: (id: string) => Promise<void>
  putQueued: (row: OfflineQueueItem) => Promise<void>
  putDead: (row: DeadLetterItem) => Promise<void>
}

function memoryMutations(): QueueMutations {
  return {
    deleteQueued: async id => {
      memory.queue.delete(id)
    },
    putQueued: async row => {
      memory.queue.set(row.id, row)
    },
    putDead: async row => {
      memory.dead.set(row.id, row)
      memory.queue.delete(row.id)
    },
  }
}

function idbMutations(db: IDBDatabase): QueueMutations {
  return {
    deleteQueued: async id => {
      await runStore(db, STORE, 'readwrite', store => {
        store.delete(id)
      })
    },
    putQueued: async row => {
      await runStore(db, STORE, 'readwrite', store => {
        store.put(row)
      })
    },
    putDead: async row => {
      await new Promise<void>((resolve, reject) => {
        const tx = db.transaction([STORE, DEAD_STORE], 'readwrite')
        tx.objectStore(DEAD_STORE).put(row)
        tx.objectStore(STORE).delete(row.id)
        tx.oncomplete = () => resolve()
        tx.onerror = () => reject(tx.error)
      })
    },
  }
}

export async function enqueueOffline(
  item: Omit<OfflineQueueItem, 'id' | 'createdAt' | 'userId' | 'idempotencyKey' | 'attemptCount'> & {
    expectedUpdatedAt?: string | null
  },
): Promise<void> {
  const row: OfflineQueueItem = {
    ...item,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    userId: currentQueueUserId(),
    idempotencyKey: crypto.randomUUID(),
    attemptCount: 0,
  }
  if (memoryFallback()) {
    memory.queue.set(row.id, row)
    return
  }
  await withStore(STORE, 'readwrite', store => {
    store.put(row)
  })
}

export async function listOfflineQueue(): Promise<OfflineQueueItem[]> {
  if (memoryFallback()) {
    return [...memory.queue.values()].sort((a, b) => a.createdAt.localeCompare(b.createdAt))
  }
  const rows = ((await withStore(STORE, 'readonly', store => store.getAll())) ?? []) as OfflineQueueItem[]
  return rows.sort((a, b) => a.createdAt.localeCompare(b.createdAt))
}

export async function listDeadLetters(): Promise<DeadLetterItem[]> {
  if (memoryFallback()) {
    return [...memory.dead.values()].sort((a, b) => a.deadAt.localeCompare(b.deadAt))
  }
  const rows = ((await withStore(DEAD_STORE, 'readonly', store => store.getAll())) ?? []) as DeadLetterItem[]
  return rows.sort((a, b) => a.deadAt.localeCompare(b.deadAt))
}

export async function discardDeadLetter(id: string): Promise<void> {
  if (memoryFallback()) {
    memory.dead.delete(id)
    return
  }
  await withStore(DEAD_STORE, 'readwrite', store => {
    store.delete(id)
  })
}

export function resetOfflineQueueMemoryForTests(): void {
  memory.queue.clear()
  memory.dead.clear()
}

export type FlushSend = (item: OfflineQueueItem) => Promise<void>

export type FlushError = Error & { status?: number; conflict?: boolean }

async function flushItems(items: OfflineQueueItem[], send: FlushSend, ops: QueueMutations) {
  const currentUser = currentQueueUserId()
  let flushed = 0
  let deadLettered = 0
  let skipped = 0
  for (const item of items) {
    if (item.userId && currentUser && item.userId !== currentUser) {
      await ops.putDead({
        ...item,
        deadAt: new Date().toISOString(),
        reason: 'user_mismatch',
      })
      deadLettered += 1
      continue
    }
    if (!item.userId) {
      await ops.putDead({
        ...item,
        deadAt: new Date().toISOString(),
        reason: 'missing_user',
      })
      deadLettered += 1
      continue
    }
    try {
      await send(item)
      await ops.deleteQueued(item.id)
      flushed += 1
    } catch (err) {
      const status = (err as FlushError).status
      const conflict = Boolean((err as FlushError).conflict) || status === 409
      const nextAttempts = (item.attemptCount || 0) + 1
      const permanent = conflict || isPermanentSyncFailure(status) || nextAttempts >= OFFLINE_QUEUE_MAX_ATTEMPTS
      if (permanent) {
        await ops.putDead({
          ...item,
          attemptCount: nextAttempts,
          lastError: err instanceof Error ? err.message : 'sync failed',
          deadAt: new Date().toISOString(),
          reason: conflict ? 'conflict' : nextAttempts >= OFFLINE_QUEUE_MAX_ATTEMPTS ? 'retry_exhausted' : 'permanent_failure',
        })
        deadLettered += 1
        continue
      }
      await ops.putQueued({
        ...item,
        attemptCount: nextAttempts,
        lastError: err instanceof Error ? err.message : 'sync failed',
      })
      skipped += 1
    }
  }
  return { flushed, deadLettered, skipped }
}

export async function flushOfflineQueue(send: FlushSend): Promise<{ flushed: number; deadLettered: number; skipped: number }> {
  if (memoryFallback()) {
    return flushItems(await listOfflineQueue(), send, memoryMutations())
  }
  const db = await openDb()
  try {
    const items = (((await runStore(db, STORE, 'readonly', store => store.getAll())) ?? []) as OfflineQueueItem[]).sort(
      (a, b) => a.createdAt.localeCompare(b.createdAt),
    )
    return await flushItems(items, send, idbMutations(db))
  } finally {
    db.close()
  }
}
