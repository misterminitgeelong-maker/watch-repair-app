import { useQuery } from '@tanstack/react-query'
import { listParentAccountSites } from '@/lib/api'

export const PARENT_ACCOUNT_SITES_QUERY_KEY = ['parent-account-sites'] as const

export type ParentAccountSitesParams = {
  limit?: number
  offset?: number
  search?: string
  region?: string
  plan_kind?: 'retail' | 'operator' | 'all'
}

export function useParentAccountSites(params: ParentAccountSitesParams = {}) {
  const {
    limit = 100,
    offset = 0,
    search,
    region,
    plan_kind = 'all',
  } = params

  return useQuery({
    queryKey: [
      ...PARENT_ACCOUNT_SITES_QUERY_KEY,
      plan_kind,
      limit,
      offset,
      search?.trim() || '',
      region?.trim() || '',
    ] as const,
    queryFn: () =>
      listParentAccountSites({
        limit,
        offset,
        search: search?.trim() || undefined,
        region: region?.trim() || undefined,
        plan_kind,
      }).then(r => r.data),
    staleTime: 120_000,
    gcTime: 300_000,
  })
}
