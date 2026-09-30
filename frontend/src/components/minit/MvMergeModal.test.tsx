import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { MvMergeCandidate } from '@/lib/api'
import { MvMergeModal } from './MvMergeModal'

const api = vi.hoisted(() => ({ preview: vi.fn(), merge: vi.fn(), operator: vi.fn() }))
vi.mock('@/lib/api', () => ({
  getMvMergePreview: api.preview, runMvMerge: api.merge, updateMvOperator: api.operator,
  formatTenantLabel: (name: string) => name,
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}))
vi.mock('@/hooks/useParentAccount', () => ({ PARENT_ACCOUNT_QUERY_KEY: ['parent-account'] }))
vi.mock('@/hooks/useParentAccountSites', () => ({ PARENT_ACCOUNT_SITES_QUERY_KEY: ['parent-sites'] }))

const van: MvMergeCandidate = {
  mv_tenant_id: 'mv', mv_name: 'Kotara (MV)', mv_owner: 'Franchisee',
  operator_tenant_id: 'old', operator_name: 'Mobile Services Kotara',
  reasons: ['phone'], preselected: true, blocked: false, network_role: 'retail',
  dispatch_paused: true, shop_phone: '0400000000', shop_email: 'owner@example.test',
  dispatch_phone: '0412345678', dispatch_phone_source: 'Mobile Services dispatch',
  dispatch_email: 'owner@example.test', proposed_plan_code: 'basic_auto_key', routes_to_move: 2,
  readiness_issues: [], preview_token: 'a'.repeat(64),
}

function show(candidates = [van]) {
  api.preview.mockResolvedValue({ data: { candidates, unmatched_operators: [] } })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MvMergeModal onClose={vi.fn()} />
  </QueryClientProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  api.merge.mockResolvedValue({ data: { results: [] } })
  api.operator.mockResolvedValue({ data: { message: 'Classified as operator' } })
})

describe('MV review and dispatch confirmation', () => {
  it('keeps directory contacts visible and merges paused by default with its preview token', async () => {
    show()
    await screen.findByLabelText('Merge Kotara (MV)')
    expect(screen.getByText(/Shop phone: 0400000000/)).toHaveTextContent('owner@example.test')
    const merge = await screen.findByRole('button', { name: 'Merge 1 pair' })
    fireEvent.click(merge)
    await waitFor(() => expect(api.merge).toHaveBeenCalledWith([{
      mv_tenant_id: 'mv', operator_tenant_id: 'old', preview_token: van.preview_token,
      dispatch_phone: '0412345678', activate_dispatch: false,
    }]))
  })

  it('clears dispatch consent when the number changes', async () => {
    show()
    const phone = await screen.findByLabelText('Dispatch mobile for Kotara (MV)')
    const consent = screen.getByLabelText(/I verified this SMS number/)
    fireEvent.click(consent)
    expect(consent).toBeChecked()
    fireEvent.change(phone, { target: { value: '0400000000' } })
    expect(consent).not.toBeChecked()
  })

  it('allows unmatched vans to be classified without activating or changing their plan', async () => {
    show([{ ...van, operator_tenant_id: null }])
    fireEvent.click(await screen.findByRole('button', { name: 'Make operator only' }))
    await waitFor(() => expect(api.operator).toHaveBeenCalledWith('mv', {
      preview_token: van.preview_token, activate_dispatch: false,
    }))
    expect(api.merge).not.toHaveBeenCalled()
  })

  it('limits preselected bulk merges to five pairs', async () => {
    show(Array.from({ length: 6 }, (_, i) => ({ ...van, mv_tenant_id: `mv-${i}`, mv_name: `Van ${i} (MV)` })))
    expect(await screen.findByRole('button', { name: 'Merge 5 pairs' })).toBeEnabled()
    expect(screen.getByLabelText('Merge Van 5 (MV)')).toBeDisabled()
  })
})
