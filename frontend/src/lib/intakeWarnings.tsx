/** Amber banner for non-fatal intake issues (upload/SMS/partial jobs). */
export function IntakeWarningBanner({ messages }: { messages: string[] }) {
  const items = messages.filter(Boolean)
  if (!items.length) return null
  return (
    <div className="rounded-lg px-3 py-3 space-y-1" style={{ backgroundColor: 'color-mix(in srgb, var(--ms-error) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--ms-error) 35%, transparent)' }}>
      <p className="text-sm font-semibold" style={{ color: 'var(--ms-error)' }}>Please note</p>
      {items.map((msg, i) => (
        <p key={i} className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>{msg}</p>
      ))}
    </div>
  )
}
