/** Amber banner for non-fatal intake issues (upload/SMS/partial jobs). */
export function IntakeWarningBanner({ messages }: { messages: string[] }) {
  const items = messages.filter(Boolean)
  if (!items.length) return null
  return (
    <div className="rounded-lg px-3 py-3 space-y-1" style={{ backgroundColor: 'rgba(201,106,90,0.12)', border: '1px solid rgba(201,106,90,0.35)' }}>
      <p className="text-sm font-semibold" style={{ color: '#C96A5A' }}>Please note</p>
      {items.map((msg, i) => (
        <p key={i} className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>{msg}</p>
      ))}
    </div>
  )
}
