/** Minimal offline mutation queue (IndexedDB) for field techs. */

const DB_NAME = 'mainspring-offline'
const STORE = 'queue'

export type OfflineQueueItem = {
  id: string
  method: string
  url: string
  body: string | null
  createdAt: string
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function enqueueOffline(item: Omit<OfflineQueueItem, 'id' | 'createdAt'>): Promise<void> {
  const db = await openDb()
  const row: OfflineQueueItem = {
    ...item,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
  }
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).put(row)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
  db.close()
}

export async function listOfflineQueue(): Promise<OfflineQueueItem[]> {
  const db = await openDb()
  const rows = await new Promise<OfflineQueueItem[]>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).getAll()
    req.onsuccess = () => resolve(req.result as OfflineQueueItem[])
    req.onerror = () => reject(req.error)
  })
  db.close()
  return rows.sort((a, b) => a.createdAt.localeCompare(b.createdAt))
}

export async function flushOfflineQueue(
  send: (item: OfflineQueueItem) => Promise<void>,
): Promise<number> {
  const items = await listOfflineQueue()
  let flushed = 0
  for (const item of items) {
    await send(item)
    const db = await openDb()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite')
      tx.objectStore(STORE).delete(item.id)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
    db.close()
    flushed += 1
  }
  return flushed
}
