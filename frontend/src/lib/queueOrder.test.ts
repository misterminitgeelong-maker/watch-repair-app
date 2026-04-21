import { describe, expect, it } from 'vitest'

import { filteredJobsIdKey, mergeQueueOrder } from './queueOrder'

describe('filteredJobsIdKey', () => {
  it('returns an order-insensitive stable key', () => {
    expect(filteredJobsIdKey(['b', 'a', 'c'])).toBe(filteredJobsIdKey(['a', 'b', 'c']))
    expect(filteredJobsIdKey(['a', 'b', 'c'])).toBe('a|b|c')
    expect(filteredJobsIdKey([])).toBe('')
  })

  it('distinguishes two same-size sets with different members (F-H3)', () => {
    // This is the exact condition the original bug relied on:
    // filteredJobs.length was the same, so the old effect didn't fire.
    const setA = ['job1', 'job2', 'job3', 'job4', 'job5']
    const setB = ['job6', 'job7', 'job8', 'job9', 'job10']
    expect(setA.length).toBe(setB.length)
    expect(filteredJobsIdKey(setA)).not.toBe(filteredJobsIdKey(setB))
  })
})

describe('mergeQueueOrder (F-H3 regression)', () => {
  it('seeds directly from sortedIds on first call', () => {
    expect(mergeQueueOrder(null, ['a', 'b', 'c'])).toEqual(['a', 'b', 'c'])
  })

  it('preserves a manual reorder for ids still present', () => {
    // User dragged the queue to [c, a, b]. New sort from server is [a, b, c].
    // We should keep the user order but drop ids no longer present.
    const previous = ['c', 'a', 'b']
    const sortedIds = ['a', 'b', 'c']
    expect(mergeQueueOrder(previous, sortedIds)).toEqual(['c', 'a', 'b'])
  })

  it('drops ids no longer in the filtered set', () => {
    // User had [c, a, b], filter now excludes b.
    const previous = ['c', 'a', 'b']
    const sortedIds = ['a', 'c']
    expect(mergeQueueOrder(previous, sortedIds)).toEqual(['c', 'a'])
  })

  it('appends newly-present ids at the tail in sort order', () => {
    // User had [c, a]. New jobs d and e arrive in default sort order [a, c, d, e].
    const previous = ['c', 'a']
    const sortedIds = ['a', 'c', 'd', 'e']
    expect(mergeQueueOrder(previous, sortedIds)).toEqual(['c', 'a', 'd', 'e'])
  })

  it('handles same-count membership swap — the F-H3 bug case', () => {
    // Old filter: 5 "due today" jobs. User drags them into [j5, j4, j3, j2, j1].
    const manual = ['j5', 'j4', 'j3', 'j2', 'j1']
    // Filter swap: still 5 jobs, but entirely different ones.
    const newSorted = ['k1', 'k2', 'k3', 'k4', 'k5']
    // Before F-H3: queueOrder stayed at the old j* list. After: fully replaced.
    expect(mergeQueueOrder(manual, newSorted)).toEqual(['k1', 'k2', 'k3', 'k4', 'k5'])
  })
})
