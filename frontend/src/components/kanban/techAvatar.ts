const TECH_PALETTE = [
  { bg: '#E6E0D2', text: '#4A3D2C' },
  { bg: '#E0DAE8', text: '#3F3556' },
  { bg: '#D8E4E0', text: '#265049' },
  { bg: '#E8DCCF', text: '#5A3B1E' },
  { bg: '#DEE3E8', text: '#334761' },
  { bg: '#E4DCD0', text: '#4F3A24' },
] as const

export function initialsOf(name?: string | null): string {
  if (!name) return '—'
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '—'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function techColor(key?: string | null): { bg: string; text: string } {
  if (!key) return { bg: 'var(--ms-border)', text: 'var(--ms-text-muted)' }
  let hash = 0
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) | 0
  const idx = Math.abs(hash) % TECH_PALETTE.length
  return TECH_PALETTE[idx]
}
