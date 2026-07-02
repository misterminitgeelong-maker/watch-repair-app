import { useQuery } from '@tanstack/react-query'
import { getMyParentAccount } from '@/lib/api'

export const PARENT_ACCOUNT_QUERY_KEY = ['parent-account-me'] as const

type UseParentAccountOptions = {
  /** When true, includes the full sites array (slow for large networks). */
  includeSites?: boolean
}

/** Shared parent-account payload; cached 2 min to avoid refetch on every HQ tab click. */
export function useParentAccount(options?: UseParentAccountOptions) {
  const includeSites = options?.includeSites ?? false
  return useQuery({
    queryKey: [...PARENT_ACCOUNT_QUERY_KEY, includeSites] as const,
    queryFn: () => getMyParentAccount({ include_sites: includeSites }).then(r => r.data),
    staleTime: 120_000,
    gcTime: 300_000,
  })
}
