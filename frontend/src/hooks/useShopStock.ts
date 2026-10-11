import { useQuery } from '@tanstack/react-query'
import { shopStockLocations } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'

/**
 * Parts stock exists only for shops in an HQ network that has the stock module.
 * Everyone else (Minit shops included) gets a 403 and sees nothing, so the query
 * only runs for shoe shops and is never retried.
 */
export function useShopStockEnabled(): boolean {
  const { hasFeature } = useAuth()
  const shoe = hasFeature('shoe')
  const q = useQuery({
    queryKey: ['shop-stock-access'],
    queryFn: () => shopStockLocations().then(r => r.data),
    enabled: shoe,
    retry: false,
    staleTime: 5 * 60 * 1000,
  })
  return shoe && q.isSuccess
}
