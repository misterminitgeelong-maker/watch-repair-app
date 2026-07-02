import { useQuery } from '@tanstack/react-query'
import { getParentLeadIngestConfig } from '@/lib/api'

export const PARENT_LEAD_INGEST_QUERY_KEY = ['parent-lead-ingest'] as const

/** Lightweight website lead ingest flags — avoids loading the full parent-account site list. */
export function useParentLeadIngest() {
  return useQuery({
    queryKey: PARENT_LEAD_INGEST_QUERY_KEY,
    queryFn: () => getParentLeadIngestConfig().then(r => r.data),
    staleTime: 120_000,
    gcTime: 300_000,
  })
}
