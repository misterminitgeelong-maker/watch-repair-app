import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api/client'
import { useAuth } from '@/context/AuthContext'

/** Unread state-hub messages plus unread announcements, for the Messages nav badge. */
export function useMessagesUnread() {
  const { tenantId } = useAuth()
  const { data = 0 } = useQuery({
    queryKey: ['messages-unread', tenantId],
    queryFn: () => api.get<{ count: number }>('/network-community/unread').then(r => r.data.count),
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: false,
  })
  return data
}
