import { rankTone, rankToneColors } from './format'

/** Instrument-style rank dial — ported from the reference VSWT dashboard's RankGauge, with
 * colors swapped from a hardcoded dark palette to Mainspring's --ms-* theme tokens. */
export function VswtRankGauge({
  rank, n, label, size = 200,
}: { rank: number | null; n: number; label: string; size?: number }) {
  const pct = rank && n > 1 ? Math.min(1, Math.max(0, (rank - 1) / (n - 1))) : 0.5
  const startAngle = -130
  const endAngle = 130
  const angle = startAngle + pct * (endAngle - startAngle)
  const cx = size / 2
  const cy = size / 2 + 6
  const r = size * 0.38

  const polar = (deg: number, radius: number): [number, number] => {
    const rad = ((deg - 90) * Math.PI) / 180
    return [cx + radius * Math.cos(rad), cy + radius * Math.sin(rad)]
  }
  const describeArc = (a0: number, a1: number, radius: number) => {
    const [x0, y0] = polar(a0, radius)
    const [x1, y1] = polar(a1, radius)
    const large = a1 - a0 > 180 ? 1 : 0
    return `M ${x0} ${y0} A ${radius} ${radius} 0 ${large} 1 ${x1} ${y1}`
  }
  const needleLen = r * 0.82
  const [nx, ny] = polar(angle, needleLen)

  const zones: { a0: number; a1: number; tone: 'good' | 'warn' | 'bad' }[] = [
    { a0: startAngle, a1: startAngle + (endAngle - startAngle) * 0.33, tone: 'good' },
    { a0: startAngle + (endAngle - startAngle) * 0.33, a1: startAngle + (endAngle - startAngle) * 0.66, tone: 'warn' },
    { a0: startAngle + (endAngle - startAngle) * 0.66, a1: endAngle, tone: 'bad' },
  ]
  const tone = rankTone(rank, n)
  const toneColors = rankToneColors(tone)

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.72} viewBox={`0 0 ${size} ${size * 0.72}`}>
        {zones.map((z, i) => (
          <path
            key={i}
            d={describeArc(z.a0, z.a1, r)}
            stroke={rankToneColors(z.tone).fg}
            strokeWidth={10}
            fill="none"
            opacity={0.85}
          />
        ))}
        <path d={describeArc(startAngle, endAngle, r + 16)} stroke="var(--ms-border)" strokeWidth={1} fill="none" />
        {[0, 0.25, 0.5, 0.75, 1].map((t, i) => {
          const a = startAngle + t * (endAngle - startAngle)
          const [x1, y1] = polar(a, r - 8)
          const [x2, y2] = polar(a, r + 6)
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--ms-text-muted)" strokeWidth={1.5} />
        })}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="var(--ms-text)" strokeWidth={3} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={6} fill="var(--ms-accent)" stroke="var(--ms-text)" strokeWidth={1} />
        <text
          x={cx} y={cy - r * 0.42} textAnchor="middle" fill={toneColors.fg}
          style={{ fontSize: size * 0.16, fontWeight: 700 }}
        >
          {rank ?? '—'}
        </text>
        <text
          x={cx} y={cy - r * 0.42 + size * 0.075} textAnchor="middle" fill="var(--ms-text-muted)"
          style={{ fontSize: size * 0.045, letterSpacing: 1 }}
        >
          OF {n}
        </text>
      </svg>
      <div
        className="text-xs uppercase tracking-wide"
        style={{ marginTop: -6, color: 'var(--ms-text-muted)' }}
      >
        {label}
      </div>
    </div>
  )
}
