import { describe, expect, it } from 'vitest'
import { DEFAULT_POS_CATEGORIES, POS_QUICK_ITEMS, filterQuickItems, quickItemsForCategories } from './posQuickItems'

describe('POS quick items by catalogue category', () => {
  it('tags every quick item with a catalogue category', () => {
    for (const item of POS_QUICK_ITEMS) {
      expect(['vehicle_key', 'general_service', 'garage_door']).toContain(item.category)
    }
  })

  it('hides garage door lines from a mobile-key technician by default', () => {
    const labels = quickItemsForCategories(DEFAULT_POS_CATEGORIES).map(i => i.label)
    expect(labels).toContain('All keys lost – Prox')
    expect(labels).toContain('Callout – min charge')
    expect(labels).not.toContain('Motor replacement')
    expect(labels).not.toContain('Spring replacement')
  })

  it('shows garage door lines once the owner enables that category', () => {
    const labels = quickItemsForCategories(['vehicle_key', 'general_service', 'garage_door']).map(i => i.label)
    expect(labels).toContain('Motor replacement')
    expect(labels).toHaveLength(POS_QUICK_ITEMS.length)
  })

  it('never drops items — a category that is off is only filtered', () => {
    expect(quickItemsForCategories(['garage_door'])).toHaveLength(10)
    expect(quickItemsForCategories([])).toHaveLength(0)
    expect(POS_QUICK_ITEMS).toHaveLength(23)
  })
})

describe('filterQuickItems', () => {
  const items = [
    { label: 'All keys lost – Prox', desc: 'Proximity key' },
    { label: 'All keys lost – TE', desc: 'TE key, no remote' },
    { label: 'Callout – min charge', desc: '30km radius' },
    { label: 'Transponder copy', desc: 'Callout charged separately' },
  ]

  it('returns everything for an empty query', () => {
    expect(filterQuickItems(items, '')).toHaveLength(4)
    expect(filterQuickItems(items, '   ')).toHaveLength(4)
  })

  it('matches on label and description, ignoring case', () => {
    expect(filterQuickItems(items, 'prox').map(i => i.label)).toEqual(['All keys lost – Prox'])
    expect(filterQuickItems(items, 'RADIUS').map(i => i.label)).toEqual(['Callout – min charge'])
  })

  it('requires every term to match somewhere, in any order', () => {
    expect(filterQuickItems(items, 'keys lost').map(i => i.label)).toEqual([
      'All keys lost – Prox',
      'All keys lost – TE',
    ])
    expect(filterQuickItems(items, 'lost prox').map(i => i.label)).toEqual(['All keys lost – Prox'])
  })

  it('ignores punctuation the user is unlikely to type', () => {
    expect(filterQuickItems(items, 'callout,').map(i => i.label)).toEqual([
      'Callout – min charge',
      'Transponder copy',
    ])
  })

  it('returns an empty list when nothing matches, without mutating the source', () => {
    expect(filterQuickItems(items, 'zzz')).toEqual([])
    expect(items).toHaveLength(4)
  })
})
