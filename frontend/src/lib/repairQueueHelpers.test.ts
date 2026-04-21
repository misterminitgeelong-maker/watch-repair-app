import { describe, expect, it, beforeEach } from 'vitest'

import {
  daysInShop,
  dayQueueStorageKey,
  getCollectionUrgency,
  getLocalDateKey,
  readDayQueueState,
  sortQueue,
  writeDayQueueState,
} from './repairQueueHelpers'

beforeEach(() => {
  try {
    localStorage.clear()
  } catch {
    // ignore
  }
})

describe('getCollectionUrgency', () => {
  it('returns 3 when no date is given', () => {
    expect(getCollectionUrgency()).toBe(3)
  })

  it('returns 0 for a past date (overdue)', () => {
    const yesterday = new Date(Date.now() - 86_400_000).toISOString()
    expect(getCollectionUrgency(yesterday)).toBe(0)
  })

  it('returns 1 for today at midnight exactly', () => {
    // The function compares against today-at-midnight: d <= today returns 1.
    const todayMidnight = new Date()
    todayMidnight.setHours(0, 0, 0, 0)
    expect(getCollectionUrgency(todayMidnight.toISOString())).toBe(1)
  })

  it('returns 2 for later-today or tomorrow-midnight', () => {
    // A time later in today is > today-midnight but <= tomorrow-midnight,
    // which the function buckets as "tomorrow" (2). This is the existing
    // behaviour; documenting it here locks it in.
    const laterToday = new Date()
    laterToday.setHours(10, 0, 0, 0)
    expect(getCollectionUrgency(laterToday.toISOString())).toBe(2)
  })

  it('returns 3 for further-out dates', () => {
    const future = new Date()
    future.setDate(future.getDate() + 30)
    expect(getCollectionUrgency(future.toISOString())).toBe(3)
  })
})

describe('sortQueue', () => {
  const makeRow = (over: Partial<{ id: string; priority: string; status: string; created_at: string; collection_date: string }>) => ({
    id: 'x',
    priority: 'normal',
    status: 'awaiting_quote',
    created_at: '2026-04-01T00:00:00Z',
    ...over,
  })

  it('puts overdue before today before later', () => {
    const yesterday = new Date(Date.now() - 86_400_000).toISOString()
    const today = new Date().toISOString()
    const later = new Date(Date.now() + 7 * 86_400_000).toISOString()
    const rows = [
      makeRow({ id: 'later', collection_date: later }),
      makeRow({ id: 'today', collection_date: today }),
      makeRow({ id: 'yday', collection_date: yesterday }),
    ]
    const sorted = sortQueue(rows)
    expect(sorted[0].id).toBe('yday')
  })

  it('breaks ties on priority: urgent < high < normal < low', () => {
    const rows = [
      makeRow({ id: 'low', priority: 'low' }),
      makeRow({ id: 'urgent', priority: 'urgent' }),
      makeRow({ id: 'normal', priority: 'normal' }),
      makeRow({ id: 'high', priority: 'high' }),
    ]
    const sorted = sortQueue(rows)
    expect(sorted.map((r) => r.id)).toEqual(['urgent', 'high', 'normal', 'low'])
  })

  it('breaks further ties on oldest created_at', () => {
    const rows = [
      makeRow({ id: 'newer', created_at: '2026-04-05T00:00:00Z' }),
      makeRow({ id: 'older', created_at: '2026-04-01T00:00:00Z' }),
    ]
    expect(sortQueue(rows).map((r) => r.id)).toEqual(['older', 'newer'])
  })
})

describe('daysInShop', () => {
  it('rounds down to whole days', () => {
    const fiveDaysAgo = new Date(Date.now() - 5 * 86_400_000).toISOString()
    expect(daysInShop(fiveDaysAgo)).toBe(5)
  })

  it('returns 0 for just-created', () => {
    expect(daysInShop(new Date().toISOString())).toBe(0)
  })
})

describe('getLocalDateKey / dayQueueStorageKey', () => {
  it('returns a y-m-d string', () => {
    const key = getLocalDateKey(new Date(2026, 3, 21))
    expect(key).toBe('2026-04-21')
  })

  it('includes mode + local date in the storage key', () => {
    const key = dayQueueStorageKey('watch')
    expect(key).toMatch(/^repairQueueDay:v1:watch:\d{4}-\d{2}-\d{2}$/)
  })
})

describe('readDayQueueState / writeDayQueueState', () => {
  it('round-trips done + stats through localStorage', () => {
    const done = new Set(['job-a', 'job-b'])
    const stats = { advanced: 3, checkedIn: 1, skipped: 2 }
    writeDayQueueState('watch', done, stats)
    const loaded = readDayQueueState('watch')
    expect(loaded.done.has('job-a')).toBe(true)
    expect(loaded.done.has('job-b')).toBe(true)
    expect(loaded.stats).toEqual(stats)
  })

  it('returns empty set + zeroed stats when storage is empty', () => {
    const loaded = readDayQueueState('shoe')
    expect(loaded.done.size).toBe(0)
    expect(loaded.stats).toEqual({ advanced: 0, checkedIn: 0, skipped: 0 })
  })

  it('is resilient to JSON garbage in storage', () => {
    localStorage.setItem(dayQueueStorageKey('watch'), 'not json')
    const loaded = readDayQueueState('watch')
    expect(loaded.done.size).toBe(0)
  })

  it('is resilient to missing stats fields', () => {
    localStorage.setItem(dayQueueStorageKey('watch'), JSON.stringify({ doneIds: ['x'] }))
    const loaded = readDayQueueState('watch')
    expect(loaded.done.has('x')).toBe(true)
    expect(loaded.stats).toEqual({ advanced: 0, checkedIn: 0, skipped: 0 })
  })
})
