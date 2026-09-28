import type { CSSProperties } from 'react'
import { Footprints, KeyRound, Watch } from 'lucide-react'
import type { CustomerPortalJob } from '@/lib/api'
import type { PortalStage } from '@/lib/portalStatus'

/** A shop's brand colour, if it is a usable hex; otherwise the portal default. */
export function portalAccentStyle(brandColor?: string | null): CSSProperties | undefined {
  const c = brandColor?.trim()
  if (!c || !/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(c)) return undefined
  return { ['--pt-accent' as string]: c }
}

export function greeting(now = new Date()): string {
  const h = now.getHours()
  if (h < 5) return 'Good evening'
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

/** Customer-facing names for the four stages. */
export const STAGE_COPY: Record<PortalStage, string> = {
  received: 'Received',
  in_progress: 'In the workshop',
  ready: 'Ready',
  collected: 'Collected',
}

export function jobIcon(type: CustomerPortalJob['type']) {
  if (type === 'shoe') return Footprints
  if (type === 'auto_key') return KeyRound
  return Watch
}

export function jobTypeLabel(type: CustomerPortalJob['type']) {
  if (type === 'shoe') return 'Shoe repair'
  if (type === 'auto_key') return 'Car keys'
  return 'Watch repair'
}

/** Mister Minit's logo (tight crop, white background) and brand colours. */
export const MINIT_LOGO_SRC = '/minit-logo-cropped.jpg'
export const MINIT_RED = '#E31837'
export const MINIT_NAVY = '#2B3990'

/** "Mister Minit Chadstone" → "Chadstone"; "" when the name is just the brand. */
export function minitBranchName(name: string | null | undefined): string {
  return (name ?? '').trim().replace(/^mister\s*minit\b\s*[-–—·:|]?\s*/i, '')
}
