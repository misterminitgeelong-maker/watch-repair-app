import { describe, it, expect } from 'vitest'
import { QueryClient } from '@tanstack/react-query'
import { applyOptimisticStatus, rollbackStatus } from './optimisticStatus'

function qc() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

describe('applyOptimisticStatus', () => {
  it('moves the job in a plain list', async () => {
    const client = qc()
    client.setQueryData(['jobs', 'all'], [
      { id: 'a', status: 'received' },
      { id: 'b', status: 'received' },
    ])

    await applyOptimisticStatus(client, ['jobs'], 'a', 'in_progress')

    expect(client.getQueryData(['jobs', 'all'])).toEqual([
      { id: 'a', status: 'in_progress' },
      { id: 'b', status: 'received' },
    ])
  })

  it('moves the job inside a paged payload too', async () => {
    const client = qc()
    client.setQueryData(['auto-key-jobs', 'page', 'active'], {
      items: [{ id: 'a', status: 'booked' }],
      total: 1,
      limit: 50,
      offset: 0,
    })

    await applyOptimisticStatus(client, ['auto-key-jobs'], 'a', 'completed')

    expect(client.getQueryData(['auto-key-jobs', 'page', 'active'])).toEqual({
      items: [{ id: 'a', status: 'completed' }],
      total: 1,
      limit: 50,
      offset: 0,
    })
  })

  it('leaves shapes it does not recognise alone', async () => {
    const client = qc()
    const counts = { received: 3, done: 1 }
    client.setQueryData(['jobs', 'tomorrow-count'], counts)

    await applyOptimisticStatus(client, ['jobs'], 'a', 'done')

    // Same object back, not a mangled copy.
    expect(client.getQueryData(['jobs', 'tomorrow-count'])).toBe(counts)
  })

  it('puts every touched list back on rollback', async () => {
    const client = qc()
    const before = [{ id: 'a', status: 'received' }]
    client.setQueryData(['jobs', 'all'], before)
    client.setQueryData(['jobs', 'dashboard'], before)

    const snapshot = await applyOptimisticStatus(client, ['jobs'], 'a', 'in_progress')
    expect(client.getQueryData<typeof before>(['jobs', 'all'])![0].status).toBe('in_progress')

    rollbackStatus(client, snapshot)
    // Content, not identity: React Query rebuilds the value via structural
    // sharing, so the restored array is an equal copy rather than the same one.
    expect(client.getQueryData(['jobs', 'all'])).toEqual(before)
    expect(client.getQueryData(['jobs', 'dashboard'])).toEqual(before)
  })

  it('snapshots only the lists it actually changed', async () => {
    const client = qc()
    client.setQueryData(['jobs', 'all'], [{ id: 'a', status: 'received' }])
    client.setQueryData(['jobs', 'other'], [{ id: 'z', status: 'received' }])

    const snapshot = await applyOptimisticStatus(client, ['jobs'], 'a', 'in_progress')
    expect(snapshot).toHaveLength(1)
  })

  it('is a no-op when the job is already in that status', async () => {
    const client = qc()
    const data = [{ id: 'a', status: 'done' }]
    client.setQueryData(['jobs', 'all'], data)

    const snapshot = await applyOptimisticStatus(client, ['jobs'], 'a', 'done')

    expect(snapshot).toHaveLength(0)
    expect(client.getQueryData(['jobs', 'all'])).toBe(data)
  })
})
