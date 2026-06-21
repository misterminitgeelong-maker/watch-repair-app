/** Australian suburb + state parsing for Google Places and plain-text addresses. */

export const AU_STATE_CODES = ['ACT', 'NSW', 'NT', 'QLD', 'SA', 'TAS', 'VIC', 'WA'] as const
export type AuStateCode = (typeof AU_STATE_CODES)[number]

export interface ParsedAuAddress {
  suburb: string | null
  stateCode: AuStateCode | null
}

const STATE_ALIASES: Record<string, AuStateCode> = {
  act: 'ACT',
  'australian capital territory': 'ACT',
  nsw: 'NSW',
  'new south wales': 'NSW',
  nt: 'NT',
  'northern territory': 'NT',
  qld: 'QLD',
  queensland: 'QLD',
  sa: 'SA',
  'south australia': 'SA',
  tas: 'TAS',
  tasmania: 'TAS',
  vic: 'VIC',
  victoria: 'VIC',
  wa: 'WA',
  'western australia': 'WA',
}

export function normalizeAuStateCode(raw: string | null | undefined): AuStateCode | null {
  const key = (raw ?? '').trim().toLowerCase()
  if (!key) return null
  return STATE_ALIASES[key] ?? null
}

type AddressComponentLike = {
  long_name?: string
  short_name?: string
  types?: string[]
}

function pickComponent(
  components: AddressComponentLike[],
  type: string,
  preferShort = false,
): string | null {
  const row = components.find(c => (c.types ?? []).includes(type))
  if (!row) return null
  const value = (preferShort ? row.short_name : row.long_name) ?? row.short_name ?? row.long_name
  return (value ?? '').trim() || null
}

function suburbFromComponents(components: AddressComponentLike[]): string | null {
  for (const type of ['locality', 'postal_town', 'sublocality_level_1', 'sublocality', 'neighborhood']) {
    const name = pickComponent(components, type)
    if (name) return name
  }
  return null
}

export function parseAuAddressFromComponents(
  components: AddressComponentLike[] | undefined | null,
): ParsedAuAddress {
  if (!components?.length) return { suburb: null, stateCode: null }
  const suburb = suburbFromComponents(components)
  const stateRaw =
    pickComponent(components, 'administrative_area_level_1', true) ??
    pickComponent(components, 'administrative_area_level_1', false)
  return {
    suburb,
    stateCode: normalizeAuStateCode(stateRaw),
  }
}

/** Best-effort parse from a formatted AU address when Places components are unavailable. */
export function parseAuAddressFromFormatted(address: string): ParsedAuAddress {
  const trimmed = address.trim()
  if (!trimmed) return { suburb: null, stateCode: null }

  const withPostcode = trimmed.match(
    /,\s*([^,]+?)\s+(ACT|NSW|NT|QLD|SA|TAS|VIC|WA)\s+\d{4}\b/i,
  )
  if (withPostcode) {
    return {
      suburb: withPostcode[1].trim(),
      stateCode: normalizeAuStateCode(withPostcode[2]),
    }
  }

  const stateOnly = trimmed.match(/,\s*([^,]+?)\s+(ACT|NSW|NT|QLD|SA|TAS|VIC|WA)\b/i)
  if (stateOnly) {
    return {
      suburb: stateOnly[1].trim(),
      stateCode: normalizeAuStateCode(stateOnly[2]),
    }
  }

  return { suburb: null, stateCode: null }
}

export interface ResolvedAuAddress extends ParsedAuAddress {
  formattedAddress: string
}
