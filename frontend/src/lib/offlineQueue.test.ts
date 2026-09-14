import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  enqueueOffline,
  flushOfflineQueue,
  listDeadLetters,
  listOfflineQueue,
  resetOfflineQueueMemoryForTests,
  userIdFromAccessToken,
  type FlushError,
} from './offlineQueue'

function tokenForUser(userId: string): string {
  const payload = btoa(JSON.stringify({ user_id: userId, sub: userId }))
  return `aaa.${payload}.sig`
}

function setUser(userId: string | null) {
  if (userId) localStorage.setItem('token', tokenForUser(userId))
  else localStorage.removeItem('token')
}

describe('offlineQueue', () => {
  beforeEach(() => {
    resetOfflineQueueMemoryForTests()
    localStorage.clear()
  })

  it('decodes user id from a JWT payload', () => {
    expect(userIdFromAccessToken(tokenForUser('user-1'))).toBe('user-1')
  })

  it('discards queued items when the current user does not match', async () => {
    setUser('tech-a')
    await enqueueOffline({ method: 'POST', url: '/v1/auto-key-jobs', body: '{}' })
    setUser('tech-b')
    const send = vi.fn()
    const result = await flushOfflineQueue(send)
    expect(send).not.toHaveBeenCalled()
    expect(result.deadLettered).toBe(1)
    expect(await listOfflineQueue()).toHaveLength(0)
    expect(await listDeadLetters()).toHaveLength(1)
    expect((await listDeadLetters())[0]?.reason).toBe('user_mismatch')
  })

  it('dead-letters a permanently failing item so later items can flush', async () => {
    setUser('tech-a')
    await enqueueOffline({ method: 'POST', url: '/v1/jobs/poison', body: '{}' })
    await enqueueOffline({ method: 'POST', url: '/v1/jobs/ok', body: '{}' })
    const send = vi.fn(async (item: { url: string }) => {
      if (item.url.includes('poison')) {
        const err: FlushError = Object.assign(new Error('Unprocessable'), { status: 422 })
        throw err
      }
    })
    const result = await flushOfflineQueue(send)
    expect(result.flushed).toBe(1)
    expect(result.deadLettered).toBe(1)
    expect(await listOfflineQueue()).toHaveLength(0)
    const dead = await listDeadLetters()
    expect(dead).toHaveLength(1)
    expect(dead[0]?.reason).toBe('permanent_failure')
  })

  it('dead-letters after retry exhaustion', async () => {
    setUser('tech-a')
    await enqueueOffline({ method: 'POST', url: '/v1/jobs/flaky', body: '{}' })
    const timeout: FlushError = Object.assign(new Error('timeout'), { status: undefined })
    for (let i = 0; i < 4; i++) {
      const once = await flushOfflineQueue(async () => {
        throw timeout
      })
      expect(once.deadLettered).toBe(0)
    }
    const last = await flushOfflineQueue(async () => {
      throw timeout
    })
    expect(last.deadLettered).toBe(1)
    expect(await listOfflineQueue()).toHaveLength(0)
  })

  it('assigns an idempotency key at enqueue time', async () => {
    setUser('tech-a')
    await enqueueOffline({ method: 'POST', url: '/v1/auto-key-jobs', body: '{}' })
    const [item] = await listOfflineQueue()
    expect(item?.idempotencyKey).toMatch(/^[0-9a-f-]{36}$/i)
    expect(item?.userId).toBe('tech-a')
  })
})
