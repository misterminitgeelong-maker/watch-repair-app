import { describe, expect, it } from 'vitest'
import { hqNavFor, MINIT_HQ_NAV } from './MinitHqSidebar'

const MINIT_MODULES = ['mobile_services', 'lead_routing', 'kpis', 'regional_reports']

describe('hqNavFor', () => {
  it('keeps Minit exactly as it was, whether settings have loaded or not', () => {
    const labels = MINIT_HQ_NAV.map(i => i.label)
    expect(hqNavFor(undefined).map(i => i.label)).toEqual(labels)
    expect(hqNavFor(MINIT_MODULES).map(i => i.label)).toEqual(labels)
    expect(labels).toEqual(['Dashboard', 'Inbox', 'Shops', 'Lead routing', 'Mobile reports', 'Reports'])
  })

  it('shows a shoe-only HQ just Shops and Shoe repairs', () => {
    expect(hqNavFor(['shoe', 'stock']).map(i => i.label)).toEqual(['Shops', 'Shoe repairs'])
  })

  it('adds Shoe repairs after the mobile links when both are on', () => {
    const labels = hqNavFor([...MINIT_MODULES, 'shoe']).map(i => i.label)
    expect(labels.slice(0, 6)).toEqual(MINIT_HQ_NAV.map(i => i.label))
    expect(labels[6]).toBe('Shoe repairs')
  })

  it('hides mobile links for modules that are off', () => {
    expect(hqNavFor(['mobile_services']).map(i => i.label)).toEqual(['Dashboard', 'Shops', 'Reports'])
  })
})
