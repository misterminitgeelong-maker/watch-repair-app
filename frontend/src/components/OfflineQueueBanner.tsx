import { useEffect, useState } from 'react'
import { listOfflineQueue, flushOfflineQueue } from '@/lib/offlineQueue'
import api from '@/lib/api/client'
import { useToast } from '@/lib/toast'

export default function OfflineQueueBanner() {
  const [pending, setPending] = useState(0)
  const [online, setOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true)
  const toast = useToast()

  async function refreshCount() {
    const items = await listOfflineQueue()
    setPending(items.length)
  }

  useEffect(() => {
    void refreshCount()
    const onOnline = () => setOnline(true)
    const onOffline = () => setOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  useEffect(() => {
    if (!online || pending === 0) return
    void (async () => {
      try {
        const n = await flushOfflineQueue(async item => {
          await api.request({
            method: item.method,
            url: item.url,
            data: item.body ? JSON.parse(item.body) : undefined,
          })
        })
        if (n > 0) toast.success(`Synced ${n} offline change${n === 1 ? '' : 's'}`)
        await refreshCount()
      } catch {
        /* keep queue */
      }
    })()
  }, [online, pending, toast])

  if (!online) {
    return (
      <div className="text-xs text-center py-1.5 px-3" style={{ backgroundColor: 'rgba(180,120,40,0.2)', color: '#6A4A10' }}>
        You are offline — changes will sync when connection returns.
        {pending > 0 ? ` (${pending} pending)` : ''}
      </div>
    )
  }
  if (pending > 0) {
    return (
      <div className="text-xs text-center py-1.5 px-3" style={{ backgroundColor: 'rgba(79,130,201,0.15)', color: '#1F4C6D' }}>
        Syncing {pending} offline change{pending === 1 ? '' : 's'}…
      </div>
    )
  }
  return null
}
