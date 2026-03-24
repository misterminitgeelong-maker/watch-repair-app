import { useInfiniteQuery, type InfiniteData } from '@tanstack/react-query'
import { DEFAULT_PAGE_SIZE } from '@/lib/api'

export function flattenInfinitePages<T>(data: InfiniteData<T[], unknown> | undefined): T[] {
  return data?.pages.flatMap((p) => p) ?? []
}

/**
 * Offset-based "load more" against APIs that return plain arrays and use limit/offset.
 * hasNextPage is true when the last page length equals pageSize.
 */
export function useOffsetPaginatedQuery<T>(options: {
  queryKey: unknown[]
  pageSize?: number
  enabled?: boolean
  queryFn: (offset: number) => Promise<T[]>
}) {
  const pageSize = options.pageSize ?? DEFAULT_PAGE_SIZE
  return useInfiniteQuery({
    queryKey: options.queryKey,
    initialPageParam: 0,
    queryFn: ({ pageParam }) => options.queryFn(pageParam as number),
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length < pageSize ? undefined : allPages.reduce((sum, p) => sum + p.length, 0),
    enabled: options.enabled ?? true,
  })
}
