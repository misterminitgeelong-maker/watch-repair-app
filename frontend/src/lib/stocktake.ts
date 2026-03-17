export const STOCK_GROUP_NAMES: Record<string, string> = {
  AA: 'LADIES HEELS',
  AB: 'MENS HEELS',
  BA: 'LADIES SOLES',
  BC: 'MENS SOLES',
  CA: 'MISC BAG REPAIRS',
  CB: 'SNEAKER CLEANING',
  CD: 'MISC SHOE REPAIRS',
  DA: 'FLAT KEYS',
  DB: 'RFID',
  DC: 'AUTO KEY REMOTE',
  DD: 'FUN KEY',
  DE: 'GARAGE GATE REMOTE',
  EA: 'ENGRAVING',
  EB: 'TAGS & PLATES',
  EC: 'COMPUTER ENGRAVING',
  FB: 'SHARPENING',
  FC: 'PHONE SERVICES',
  FD: 'CASH DIFFERENCES',
  FF: 'MISC SERVICES',
  GA: 'SHOE CARE',
  HA: 'KEY RINGS',
  IA: 'LOCKS & SECURITY',
  JA: 'GIFTWARE',
  JB: 'SUNDRY MERCHANDISE',
  KA: 'PROMOTIONAL',
  KB: 'CHARITY',
  NA: 'WATCH REPAIRS',
  NB: 'WATCH BATTERY FITTED',
  NC: 'WATCH BANDS',
  ND: '3RD PARTY WATCH',
  NE: 'BATTERY SUPPLY ONLY',
  NF: 'OTHER BATTERY FITTED',
}

export const STOCK_GROUP_OPTIONS = Object.entries(STOCK_GROUP_NAMES).map(([code, name]) => ({ code, name }))

export function buildStockFullDescription(...parts: Array<string | undefined>) {
  const seen = new Set<string>()
  const ordered: string[] = []
  for (const part of parts) {
    const cleaned = (part ?? '').trim().replace(/\s+/g, ' ')
    if (!cleaned) continue
    const token = cleaned.toLowerCase()
    if (seen.has(token)) continue
    seen.add(token)
    ordered.push(cleaned)
  }
  return ordered.join(' | ')
}

export function varianceTone(varianceQty: number | null | undefined) {
  if (varianceQty == null) return 'neutral'
  if (varianceQty === 0) return 'match'
  if (varianceQty < 0) return 'shortage'
  return 'over'
}
