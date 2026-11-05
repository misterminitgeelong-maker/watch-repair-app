import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Check, Clock, CreditCard, MessageSquare, PartyPopper } from 'lucide-react'
import MedalPreview from '@/components/engraving/MedalPreview'
import { engravingPlaceText, getPublicEngravingOrder, startPublicEngravingCheckout, type PublicEngravingOrder } from '@/lib/api/engraving'
import { formatCents } from '@/lib/utils'

function headline(order: PublicEngravingOrder): { title: string; sub: string } {
  switch (order.status) {
    case 'ready':
      return { title: 'Ready to collect', sub: `Show order ${order.order_number} at the stall.` }
    case 'collected':
      return { title: 'Collected', sub: 'Enjoy the medal!' }
    case 'cancelled':
      return { title: 'Order cancelled', sub: 'Please ask at the stall if this is a mistake.' }
    case 'engraving':
      return { title: 'Engraving now', sub: `Medal ${Math.min(order.medals_done + 1, order.qty)} of ${order.qty} is on the laser.` }
    default: {
      const pos = order.queue_position ?? 1
      const wait = order.wait_minutes ?? 0
      return {
        title: "You're in the queue",
        sub: `${pos === 1 ? 'Next up' : `${pos}${ordinal(pos)} in line`} · about ${Math.max(5, wait)} minutes`,
      }
    }
  }
}

function ordinal(n: number): string {
  const v = n % 100
  if (v >= 11 && v <= 13) return 'th'
  return ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th'
}

export default function PublicEngravingStatusPage() {
  const { statusToken } = useParams<{ statusToken: string }>()
  const [searchParams] = useSearchParams()
  const justPaid = searchParams.get('paid') === '1'
  const [payBusy, setPayBusy] = useState(false)
  const [payError, setPayError] = useState('')
  const { data: order, isLoading, isError } = useQuery({
    queryKey: ['public-engraving-order', statusToken],
    queryFn: () => getPublicEngravingOrder(statusToken!).then((r) => r.data),
    enabled: !!statusToken,
    retry: false,
    // Live: keeps updating while the parent watches the races.
    // Keep polling after returning from card checkout until the payment shows up.
    refetchInterval: (q) => (q.state.data && !(justPaid && !q.state.data.paid) && ['collected', 'cancelled'].includes(q.state.data.status) ? false : 10000),
  })

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-muted)' }}>
        <Clock className="animate-spin" size={28} aria-label="Loading" />
      </div>
    )
  }
  if (isError || !order) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4" style={{ backgroundColor: 'var(--ms-bg)' }}>
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold mb-2" style={{ color: 'var(--ms-text)' }}>Order not found</h1>
          <p style={{ color: 'var(--ms-text-muted)' }}>Please ask at the engraving stall.</p>
        </div>
      </div>
    )
  }

  async function payOnline() {
    setPayBusy(true)
    setPayError('')
    try {
      const res = await startPublicEngravingCheckout(statusToken!)
      window.location.assign(res.data.checkout_url)
    } catch {
      setPayError("Couldn't start card payment. Try again, or pay at the stall.")
      setPayBusy(false)
    }
  }

  const { title, sub } = headline(order)
  const ready = order.status === 'ready'
  const done = ready || order.status === 'collected'
  const rows: [string, string][] = [
    ['Name', order.athlete_name],
    ['Second line', order.line2 || '—'],
    ['Place', engravingPlaceText(order.place) || '—'],
    ...(order.ticket_number ? ([['Ticket', order.ticket_number]] as [string, string][]) : []),
    ['Medals', String(order.qty)],
    [order.paid ? 'Paid' : order.can_pay_online ? 'To pay' : 'To pay at the stall', formatCents(order.amount_cents)],
  ]

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}>
      <header className="px-5 py-4" style={{ background: 'var(--ms-ink, #0A0A0A)', color: '#fff', borderBottom: '2px solid #C99A3B' }}>
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] leading-tight">Medal engraving</p>
        <p className="text-xs opacity-80">{[order.shop_name, order.event_name].filter(Boolean).join(' · ')}</p>
      </header>

      <main className="mx-auto max-w-md px-5 py-7 flex flex-col gap-5" aria-live="polite">
        <div className="flex flex-col items-center gap-2 text-center">
          <div
            className="h-14 w-14 rounded-full flex items-center justify-center"
            style={{ background: done ? 'var(--ms-success, #1F6F43)' : 'var(--ms-accent)', color: '#fff' }}
          >
            {ready ? <PartyPopper size={28} aria-hidden /> : done ? <Check size={28} aria-hidden /> : <Clock size={28} aria-hidden />}
          </div>
          <h1 className="text-4xl leading-none" style={{ fontFamily: 'var(--ms-font-display)', fontWeight: 400 }}>{title}</h1>
          <p className="text-[15px]" style={{ color: 'var(--ms-text-mid)' }}>{sub}</p>
        </div>

        <section aria-label="Your order number" className="rounded-[var(--ms-radius)] p-5 flex flex-col items-center gap-1" style={{ background: 'var(--ms-ink, #0A0A0A)', color: '#fff', borderBottom: '2px solid #C99A3B' }}>
          <span className="text-xs font-semibold uppercase tracking-[0.12em] opacity-80">Show this at the stall</span>
          <span className="text-6xl leading-none tracking-wide" style={{ fontFamily: 'var(--ms-font-display)', fontWeight: 400 }}>{order.order_number}</span>
        </section>

        <div className="flex justify-center">
          <MedalPreview name={order.athlete_name} line2={order.line2} place={order.place} size={180} />
        </div>

        <section aria-label="Order details" className="rounded-[var(--ms-radius)] px-4" style={{ background: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
          {rows.map(([label, value], i) => (
            <div key={label} className="flex justify-between gap-3 py-3 text-sm" style={i ? { borderTop: '1px solid var(--ms-border)' } : undefined}>
              <span style={{ color: 'var(--ms-text-mid)' }}>{label}</span>
              <span className="font-semibold text-right">{value}</span>
            </div>
          ))}
        </section>

        {order.can_pay_online && (
          <section aria-label="Pay online" className="rounded-[var(--ms-radius)] px-4 py-4 flex flex-col gap-2" style={{ background: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
            {justPaid && <p className="text-sm" style={{ color: 'var(--ms-text-mid)' }}>Thanks! Confirming your payment…</p>}
            <button
              type="button"
              onClick={payOnline}
              disabled={payBusy}
              className="flex items-center justify-center gap-2 rounded-[var(--ms-radius)] px-4 py-3 text-[15px] font-semibold disabled:opacity-60"
              style={{ background: 'var(--ms-accent)', color: '#fff' }}
            >
              <CreditCard size={18} aria-hidden />
              {payBusy ? 'Opening payment…' : `Pay ${formatCents(order.amount_due_cents)} by card`}
            </button>
            {order.group_members.length > 0 && (
              <p className="text-xs text-center" style={{ color: 'var(--ms-text-mid)' }}>Covers all medals ordered together.</p>
            )}
            <p className="text-xs text-center" style={{ color: 'var(--ms-text-mid)' }}>Or pay at the stall when you collect.</p>
            {payError && <p className="text-sm text-center" role="alert" style={{ color: 'var(--ms-error)' }}>{payError}</p>}
          </section>
        )}

        {order.group_members.length > 0 && (
          <section aria-label="Your other medals" className="rounded-[var(--ms-radius)] px-4 py-3 flex flex-col gap-1" style={{ background: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}>
            <p className="text-xs font-bold uppercase tracking-[0.12em]" style={{ color: 'var(--ms-text-mid)' }}>Ordered together</p>
            {order.group_members.map((m) => (
              <Link key={m.order_number} to={`/engrave/o/${m.status_token}`} className="flex justify-between gap-3 py-2 text-sm" style={{ borderTop: '1px solid var(--ms-border)' }}>
                <span className="font-semibold">{m.order_number} · {m.athlete_name}</span>
                <span style={{ color: 'var(--ms-text-mid)' }}>{m.status === 'ready' ? 'Ready' : m.status === 'collected' ? 'Collected' : m.status === 'engraving' ? 'Engraving' : m.status === 'cancelled' ? 'Cancelled' : 'In queue'}</span>
              </Link>
            ))}
          </section>
        )}

        {!done && (
          <div className="flex items-start gap-3 rounded-[var(--ms-radius)] px-4 py-3.5 text-sm leading-snug" style={{ background: 'var(--ms-badge-blue-bg, #DCE8FB)', color: 'var(--ms-badge-blue-text, #1E3A8A)' }}>
            <MessageSquare size={20} className="shrink-0" aria-hidden />
            <span>
              {order.phone_masked
                ? <>We'll text <strong>{order.phone_masked}</strong> when it's ready. This page also updates by itself.</>
                : <>Keep this page open, it updates by itself when your medal is ready.</>}
            </span>
          </div>
        )}

        <p className="text-center text-xs" style={{ color: 'var(--ms-text-mid)' }}>
          Bookmark this page to check back.
        </p>
      </main>
    </div>
  )
}
