import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useInboxCount } from './useInboxCount'

vi.mock('@/context/AuthContext', () => ({ useAuth: () => ({ minitHqUi: true, tenantId: 'hq' }) }))
vi.mock('@/lib/api', () => ({
  getInboxCount: vi.fn().mockResolvedValue({ data: { count: 2 } }),
  getInboundEmailCount: vi.fn().mockResolvedValue({ data: { count: 620 } }),
}))

describe('Support office Inbox badge', () => {
  it('uses the complete email count rather than a page of email rows', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
    const result = renderHook(useInboxCount, { wrapper })
    await waitFor(() => expect(result.result.current).toBe(622))
  })
})
