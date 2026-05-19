import { useQuery } from '@tanstack/react-query'
import { getMyParentAccount } from '@/lib/api'

export const PARENT_ACCOUNT_QUERY_KEY = ['parent-account-me'] as const

/** Shared parent-account payload; cached 2 min to avoid refetch on every HQ tab click. */
export function useParentAccount() {
  return useQuery({
    queryKey: PARENT_ACCOUNT_QUERY_KEY,
    queryFn: () => getMyParentAccount().then(r => r.data),
    staleTime: 120_000,
    gcTime: 300_000,
  })
}
