import { engravingPlaceText, type EngravingEvent, type EngravingOrder } from '@/lib/api/engraving'
import { formatCents } from '@/lib/utils'

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c] as string)

const BASE_CSS = `
  body{font-family:'Plus Jakarta Sans',system-ui,sans-serif;color:#0A0A0A;margin:0;padding:16px}
  h1{font-family:'Instrument Serif',Georgia,serif;font-weight:400;margin:0}
  .rule{height:2px;background:#C99A3B;margin:6px 0 10px}
`

function openPrint(title: string, css: string, body: string): boolean {
  const w = window.open('', '_blank', 'width=800,height=900')
  if (!w) return false
  w.document.write(`<!doctype html><html><head><title>${esc(title)}</title><style>${BASE_CSS}${css}</style></head><body>${body}</body></html>`)
  w.document.close()
  w.focus()
  w.onload = () => w.print()
  return true
}

/** Sort key: the orders in a bunch stay together, in order-number order. */
export function ordersInBunch(order: EngravingOrder, all: EngravingOrder[]): EngravingOrder[] {
  const mates = order.group_id ? all.filter((o) => o.group_id === order.group_id) : [order]
  return [...mates].sort((a, b) => a.order_seq - b.order_seq)
}

/** A slip for the engraver to keep in the customer's tub: who it is, what to engrave, paid or not. */
export function printTubTicket(event: EngravingEvent, bunch: EngravingOrder[]): boolean {
  const first = bunch[0]
  const phone = bunch.find((o) => o.phone)?.phone
  const owing = bunch.filter((o) => !o.paid).reduce((sum, o) => sum + o.amount_cents, 0)
  const rows = bunch
    .map((o) => {
      const detail = [o.line2, engravingPlaceText(o.place)].filter(Boolean).join(' · ')
      return `<div class="row"><span class="num">${esc(o.order_number)}</span><span class="who"><b>${esc(o.athlete_name)}</b>${detail ? `<br>${esc(detail)}` : ''}</span><span class="qty">×${o.qty}</span></div>`
    })
    .join('')
  const css = `
    .ticket{border:2px dashed #0A0A0A;padding:16px;max-width:420px}
    .tk{font-size:56px;line-height:1}
    .row{display:flex;gap:12px;align-items:baseline;padding:8px 0;border-top:1px solid #ccc;font-size:18px}
    .num{font-weight:700;min-width:70px}.who{flex:1}.qty{font-weight:700}
    .foot{margin-top:10px;font-size:16px;display:flex;justify-content:space-between}
  `
  return openPrint(
    `Tub ticket ${first.ticket_number ?? first.order_number}`,
    css,
    `<div class="ticket"><div style="font-size:12px;text-transform:uppercase;letter-spacing:.12em">${esc(event.name)}</div>
      <h1 class="tk">${first.ticket_number ? `Ticket ${esc(first.ticket_number)}` : esc(first.order_number)}</h1><div class="rule"></div>
      ${rows}
      <div class="foot"><span>${owing > 0 ? `<b>UNPAID ${esc(formatCents(owing))}</b>` : 'Paid'}</span><span>${phone ? `Mobile ends ${esc(phone.slice(-4))}` : 'No mobile'}</span></div></div>`,
  )
}

/** A sheet of numbered tear-off tickets (two matching halves) to hand out at the stall. */
export function printTicketSheet(eventName: string, from: number, count: number): boolean {
  const tickets = Array.from({ length: count }, (_, i) => from + i)
  const half = (n: number, label: string) =>
    `<div class="half"><div class="lab">${esc(label)}</div><div class="n">${n}</div></div>`
  const css = `
    @page{margin:10mm}
    .grid{display:grid;grid-template-columns:repeat(2,1fr);gap:0}
    .t{display:flex;border:1px dashed #555;margin:-1px 0 0 -1px;height:22mm}
    .half{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center}
    .half+.half{border-left:2px dotted #555}
    .lab{font-size:9px;text-transform:uppercase;letter-spacing:.1em}
    .n{font-family:'Instrument Serif',Georgia,serif;font-size:34px;line-height:1}
    .head{font-size:12px;margin-bottom:8px}
  `
  return openPrint(
    'Engraving tickets',
    css,
    `<div class="head">${esc(eventName)} · tear-off tickets. Keep the left half, put the right half in the tub.</div>
     <div class="grid">${tickets.map((n) => `<div class="t">${half(n, 'Keep')}${half(n, 'In the tub')}</div>`).join('')}</div>`,
  )
}
