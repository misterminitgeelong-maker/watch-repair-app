type AklComplexityPillProps = {
  complexity: string
  className?: string
}

export function parseAklComplexity(techNotes?: string | null): string | null {
  if (!techNotes) return null
  const m = techNotes.match(/AKL complexity:\s*([^\n]+)/i)
  return m ? m[1].trim() : null
}

function styleForComplexity(complexity: string): { bg: string; color: string } {
  const c = complexity.toLowerCase()
  if (c.includes('very high') || c.includes('refer')) return { bg: 'rgba(201,106,90,0.15)', color: '#C96A5A' }
  if (c.includes('high')) return { bg: 'rgba(201,106,90,0.10)', color: '#B85A4A' }
  if (c.includes('medium')) return { bg: 'rgba(201,162,72,0.12)', color: '#9A7220' }
  return { bg: 'rgba(120,180,120,0.15)', color: '#4A8A4A' }
}

export function AklComplexityPill({ complexity, className = '' }: AklComplexityPillProps) {
  const { bg, color } = styleForComplexity(complexity)
  return (
    <span
      className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold whitespace-nowrap ${className}`.trim()}
      style={{ backgroundColor: bg, color }}
    >
      {complexity}
    </span>
  )
}
