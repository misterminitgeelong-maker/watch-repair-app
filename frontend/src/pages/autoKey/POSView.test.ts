import { describe, expect, it } from 'vitest'
import { DEFAULT_POS_CATEGORIES, POS_QUICK_ITEMS, quickItemsForCategories } from './POSView'

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
