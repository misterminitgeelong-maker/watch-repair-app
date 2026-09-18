import { useEffect, useState } from 'react'
import axios from 'axios'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { listOfflineQueue, listDeadLetters, flushOfflineQueue, discardDeadLetter, type FlushError } from '@/lib/offlineQueue'
import api from '@/lib/api/client'
import { useToast } from '@/lib/toast'

export default function OfflineQueueBanner() {
  const [pending, setPending] = useState(0)
  const [dead, setDead] = useState(0)
  // ConnectivityBanner owns the "you are offline" message app-wide; this banner
  // only reports what the queue is doing about it.
  const { online } = useOnlineStatus()
  const toast = useToast()

  async function refreshCount() {
    const [items, deadItems] = await Promise.all([listOfflineQueue(), listDeadLetters()])
    setPending(items.length)
    setDead(deadItems.length)
  }

  useEffect(() => {
    void refreshCount()
  }, [])

  useEffect(() => {
    if (!online || pending === 0) return
    void (async () => {
      try {
        const result = await flushOfflineQueue(async item => {
          try {
            await api.request({
              method: item.method,
              url: item.url,
              data: item.body ? JSON.parse(item.body) : undefined,
              headers: {
                'Idempotency-Key': item.idempotencyKey,
                'X-Queued-At': item.createdAt,
                ...(item.expectedUpdatedAt ? { 'X-Expected-Updated-At': item.expectedUpdatedAt } : {}),
              },
            })
          } catch (err) {
            const wrapped: FlushError = Object.assign(new Error(axios.isAxiosError(err) ? err.message : 'sync failed'), {
              status: axios.isAxiosError(err) ? err.response?.status : undefined,
              conflict: axios.isAxiosError(err) && err.response?.status === 409,
            })
            throw wrapped
          }
        })
        if (result.flushed > 0) toast.success(`Synced ${result.flushed} offline change${result.flushed === 1 ? '' : 's'}`)
        if (result.deadLettered > 0) {
          toast.error(`${result.deadLettered} offline change${result.deadLettered === 1 ? '' : 's'} could not sync`)
        }
        await refreshCount()
      } catch {
        await refreshCount()
      }
    })()
  }, [online, pending, toast])

  if (!online) {
    if (pending === 0) return null
    return (
      <div role="status" aria-live="polite" className="text-xs text-center py-1.5 px-3" style={{ backgroundColor: 'rgba(180,120,40,0.2)', color: '#6A4A10' }}>
        {pending} change{pending === 1 ? '' : 's'} waiting to sync when the connection returns.
      </div>
    )
  }
  if (pending > 0) {
    return (
      <div role="status" aria-live="polite" className="text-xs text-center py-1.5 px-3" style={{ backgroundColor: 'rgba(79,130,201,0.15)', color: '#1F4C6D' }}>
        Syncing {pending} offline change{pending === 1 ? '' : 's'}…
      </div>
    )
  }
  if (dead > 0) {
    return (
      <div className="text-xs text-center py-1.5 px-3" style={{ backgroundColor: 'rgba(180,60,40,0.12)', color: '#7A2410' }}>
        {dead} offline change{dead === 1 ? '' : 's'} could not sync
        {' · '}
        <button
          type="button"
          className="underline"
          onClick={() => {
            void (async () => {
              const items = await listDeadLetters()
              await Promise.all(items.map(item => discardDeadLetter(item.id)))
              await refreshCount()
            })()
          }}
        >
          dismiss
        </button>
      </div>
    )
  }
  return null
}
