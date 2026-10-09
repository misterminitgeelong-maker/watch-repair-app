import { useQuery } from '@tanstack/react-query'
import { getMyHqConfig } from '@/lib/api'

export const HQ_CONFIG_QUERY_KEY = ['hq-config-me'] as const

/** The signed-in HQ's own settings: which areas it has switched on, and how it is branded. */
export function useHqConfig(enabled = true) {
  return useQuery({
    queryKey: HQ_CONFIG_QUERY_KEY,
    queryFn: () => getMyHqConfig().then(r => r.data),
    enabled,
    staleTime: 300_000,
    retry: false,
  })
}

/** True until the config says otherwise, so a slow or failed fetch never hides Minit's existing menu. */
export function hqHasModule(modules: readonly string[] | undefined, module: string): boolean {
  return modules ? modules.includes(module) : true
}
