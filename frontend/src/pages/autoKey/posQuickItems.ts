import type { MobileCatalogueCategory } from '@/lib/api'

/**
 * Quick-add items, tagged with the catalogue category they belong to. Garage
 * door lines used to sit in this list untagged, so every mobile-key technician
 * saw them; the POS now shows only the categories the shop has enabled
 * (owner setting under Toolkit > POS catalogue). Nothing is deleted.
 */
export const POS_QUICK_ITEMS: readonly { label: string; desc: string; price: number; category: MobileCatalogueCategory }[] = [
  // General service (Mobile Services Suggested Pricing 2026)
  { label: 'Callout – min charge', desc: '30km radius', price: 5000, category: 'general_service' },
  { label: 'Callout – next 30km', desc: 'Additional distance band', price: 5000, category: 'general_service' },
  { label: 'Gain entry', desc: 'Callout charged separately', price: 10000, category: 'general_service' },
  { label: 'Lishi pick & decode', desc: 'Incl. callout', price: 25000, category: 'vehicle_key' },
  { label: 'Diagnostic fee', desc: 'Callout charged separately', price: 10000, category: 'general_service' },
  { label: 'Transponder copy', desc: 'Callout charged separately', price: 9000, category: 'vehicle_key' },
  { label: 'Transponder gen/prog', desc: 'Incl. callout', price: 25000, category: 'vehicle_key' },
  { label: 'Cut and prog', desc: 'Customer supplied key', price: 25000, category: 'vehicle_key' },
  { label: 'All keys lost – TE', desc: 'TE key, no remote', price: 30000, category: 'vehicle_key' },
  { label: 'All keys lost – Basic', desc: 'Manual remote code chip from car', price: 38000, category: 'vehicle_key' },
  { label: 'All keys lost – Prox', desc: 'Proximity key', price: 48000, category: 'vehicle_key' },
  { label: 'Lock rekey', desc: 'Per lock', price: 15000, category: 'general_service' },
  { label: 'Smart cable prog', desc: 'Nissan/Renault/Toyota/Chrysler, incl. callout', price: 65000, category: 'vehicle_key' },
  // Garage servicing
  { label: 'Door service', desc: 'Lubricate and tighten fasteners', price: 22000, category: 'garage_door' },
  { label: 'Weather seal', desc: 'Replace bottom rubber weather seal', price: 40000, category: 'garage_door' },
  { label: 'Door lock', desc: 'Replace roller/tilt lock', price: 35000, category: 'garage_door' },
  { label: 'Cables', desc: 'Replace cables both sides', price: 33000, category: 'garage_door' },
  { label: 'Hinge replacement', desc: 'Replace broken hinges', price: 17500, category: 'garage_door' },
  { label: 'Spring re-tension', desc: 'Tension and balance door', price: 15000, category: 'garage_door' },
  { label: 'Wheel replacement', desc: 'Replace broken wheels', price: 17500, category: 'garage_door' },
  { label: 'Motor calibration', desc: 'Reset limits and sensitivity', price: 15000, category: 'garage_door' },
  { label: 'Spring replacement', desc: 'Replace spring assembly', price: 45000, category: 'garage_door' },
  { label: 'Motor replacement', desc: 'Swap out motor', price: 80000, category: 'garage_door' },
]

export const DEFAULT_POS_CATEGORIES: readonly MobileCatalogueCategory[] = ['vehicle_key', 'general_service']

/** Quick items for the categories a shop sells, in catalogue order. */
export function quickItemsForCategories(enabled: readonly MobileCatalogueCategory[]) {
  return POS_QUICK_ITEMS.filter(item => enabled.includes(item.category))
}
