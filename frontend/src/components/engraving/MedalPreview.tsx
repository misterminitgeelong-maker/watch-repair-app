import { engravingPlaceText, medalNameSize, type EngravingPlace } from '@/lib/api/engraving'

interface MedalPreviewProps {
  name: string
  line2?: string | null
  place?: EngravingPlace | string
  size?: number
}

/** The back of a medal with the engraving laid out as it will be lasered. */
export default function MedalPreview({ name, line2, place = 'None', size = 220 }: MedalPreviewProps) {
  const scale = size / 220
  const shownName = name.trim() || 'Athlete name'
  const shownLine2 = (line2 ?? '').trim()
  const placeText = engravingPlaceText(place)
  return (
    <div
      role="img"
      aria-label={`Medal preview: ${[shownName, shownLine2, placeText].filter(Boolean).join(', ')}`}
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: '#D9A932',
        border: `${Math.max(3, Math.round(6 * scale))}px solid #B08419`,
        boxSizing: 'border-box',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          width: '82%',
          height: '82%',
          borderRadius: '50%',
          border: '1px solid #B08419',
          boxSizing: 'border-box',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 6 * scale,
          padding: 14 * scale,
          textAlign: 'center',
          color: '#3A2A07',
          overflow: 'hidden',
        }}
      >
        <span style={{ fontWeight: 700, fontSize: medalNameSize(shownName, 30 * scale), lineHeight: 1.05, wordBreak: 'break-word' }}>
          {shownName}
        </span>
        {shownLine2 && <span style={{ fontSize: 13 * scale, fontWeight: 500 }}>{shownLine2}</span>}
        {placeText && (
          <span style={{ fontSize: 11 * scale, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            {placeText}
          </span>
        )}
      </div>
    </div>
  )
}
