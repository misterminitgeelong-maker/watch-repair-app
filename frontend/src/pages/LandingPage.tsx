import { useEffect, useMemo, useRef, useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { Wrench, Scissors, KeyRound } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

/**
 * Marketing landing page for mainspring.au.
 *
 * Deliberately editorial — stark rules, oatmeal + vermilion, zero border-radius,
 * zero shadows — to read as the opposite of the AI-heavy, blue/white repair-SaaS
 * category. This palette is marketing-only: it must never leak into the in-app
 * "Refined Warmth" (--ms-*) token set, and the app's tokens must never leak here.
 * All colours below are scoped under .mkt-landing.
 */

const MKT = {
  paper: '#F7F7F4',
  oatmeal: '#EBE6DC',
  oatmealDeep: '#E2DACA',
  oatmealPanel: '#F1EEE7',
  ink: '#0A0A0A',
  vermilion: '#E8452A',
  vermilionDeep: '#B32D16',
  textBody: '#4A4A46',
  textMuted: '#6E6E68',
  ruleMid: '#D8D6CE',
  ruleLight: '#E4E2DA',
  greyChip: '#C4C2BA',
  statusGrey: '#6B7280',
  white: '#FFFFFF',
} as const

const DOTS: Record<string, string> = {
  wait: MKT.vermilion,
  progress: MKT.ink,
  done: MKT.statusGrey,
  neutral: MKT.greyChip,
}

const MARKETING_CSS = `
.mkt-landing {
  --mkt-paper: ${MKT.paper};
  --mkt-oatmeal: ${MKT.oatmeal};
  --mkt-oatmeal-deep: ${MKT.oatmealDeep};
  --mkt-oatmeal-panel: ${MKT.oatmealPanel};
  --mkt-oatmeal-hover: #E1DACB;
  --mkt-ink: ${MKT.ink};
  --mkt-ink-hover: #2E2E2B;
  --mkt-ink-row-hover: #EFEEE7;
  --mkt-vermilion: ${MKT.vermilion};
  --mkt-vermilion-hover: #FF5636;
  --mkt-vermilion-deep: ${MKT.vermilionDeep};
  font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
  background: var(--mkt-paper);
  color: var(--mkt-ink);
}
.mkt-landing * { box-sizing: border-box; }
.mkt-serif { font-family: Georgia, 'Palatino Linotype', Palatino, serif; }

@keyframes mktPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.mkt-pulse-dot { animation: mktPulse 1.6s ease-in-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .mkt-pulse-dot { animation: none; }
}

.mkt-reveal {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.7s cubic-bezier(.22,.68,0,1), transform 0.7s cubic-bezier(.22,.68,0,1);
}
.mkt-reveal.mkt-shown { opacity: 1; transform: translateY(0); }
@media (prefers-reduced-motion: reduce) {
  .mkt-reveal { opacity: 1 !important; transform: none !important; transition: none !important; }
}

.mkt-landing a { text-decoration: none; }

.mkt-nav-cta { background: var(--mkt-ink); color: var(--mkt-paper); transition: background 160ms ease; }
.mkt-nav-cta:hover { background: var(--mkt-vermilion); }

.mkt-btn-primary { background: var(--mkt-vermilion); color: var(--mkt-ink); transition: background 160ms ease; }
.mkt-btn-primary:hover { background: var(--mkt-vermilion-hover); }

.mkt-btn-outline-ink { background: transparent; color: var(--mkt-ink); border: 1px solid var(--mkt-ink); transition: background 160ms ease; }
.mkt-btn-outline-ink:hover { background: var(--mkt-oatmeal-hover); }

.mkt-btn-close-primary { background: var(--mkt-ink); color: var(--mkt-white); transition: background 160ms ease; }
.mkt-btn-close-primary:hover { background: var(--mkt-ink-hover); }

.mkt-btn-close-outline { background: transparent; color: var(--mkt-ink); border: 1px solid var(--mkt-ink); transition: background 160ms ease; }
.mkt-btn-close-outline:hover { background: rgba(10,10,10,0.08); }

.mkt-row-hover { transition: background 120ms ease; }
.mkt-row-hover:hover { background: var(--mkt-ink-row-hover); }

.mkt-pricing-cta { background: var(--mkt-vermilion); color: var(--mkt-ink); transition: background 160ms ease; }
.mkt-pricing-cta:hover { background: var(--mkt-vermilion-hover); }

.mkt-tab:focus-visible,
.mkt-btn-primary:focus-visible,
.mkt-btn-outline-ink:focus-visible,
.mkt-nav-cta:focus-visible,
.mkt-pricing-cta:focus-visible,
.mkt-btn-close-primary:focus-visible,
.mkt-btn-close-outline:focus-visible {
  outline: 2px solid var(--mkt-vermilion);
  outline-offset: 2px;
}
`

/* ─── Demo data — all illustrative, hard-coded; the landing page makes no API calls ─── */

const JOBS_COLS = ['Job', 'Item / service', 'Customer', 'Status', 'Value']

const JOB_LIST = [
  { number: '00142', title: 'Rolex Datejust — full service', customer: 'J. Smith', status: 'In progress', tone: 'progress', value: 'A$465' },
  { number: '00141', title: 'Seiko SNK809 — battery + test', customer: 'M. Patel', status: 'Awaiting go-ahead', tone: 'wait', value: 'A$45' },
  { number: '00140', title: 'Nike Air Max — resole', customer: 'T. Nguyen', status: 'In progress', tone: 'progress', value: 'A$120' },
  { number: '00139', title: 'Omega Speedmaster — gaskets', customer: 'A. Williams', status: 'Ready', tone: 'done', value: 'A$280' },
  { number: '00138', title: 'BMW 3 Series — key duplication', customer: 'S. Lee', status: 'Awaiting go-ahead', tone: 'wait', value: 'A$310' },
  { number: '00137', title: 'Tissot PRX — bracelet resize', customer: 'K. Doan', status: 'Booked in', tone: 'neutral', value: 'A$35' },
  { number: '00135', title: 'Cartier Tank — crystal replace', customer: 'H. Osei', status: 'Invoiced', tone: 'done', value: 'A$390' },
] as const

const STAT_CARDS = [
  { label: 'All active jobs', value: '24', helper: 'Watch 12 · Shoe 8 · Keys 4' },
  { label: 'Quotes awaiting action', value: '7', helper: '' },
  { label: 'Open invoices', value: '11', helper: 'A$4,820 awaiting payment' },
  { label: 'Outstanding work value', value: 'A$12,400', helper: '5 jobs waiting on approval' },
]

const LEDGER = [
  { n: '01', label: 'Intake', body: 'Photograph, match the customer, pick the service from your own catalogue. Ninety seconds at the counter.' },
  { n: '02', label: 'Quote', body: 'Text a link. The customer taps approve and the job moves itself onto the bench.' },
  { n: '03', label: 'Bench', body: 'Parts, pressure tests and turnaround clocks stay on the ticket, not in your head.' },
  { n: '04', label: 'Money', body: 'Invoice from the ticket. See what is billed, recovered, and still to chase.' },
]

const LIFECYCLE = [
  { label: 'Booked in', note: 'Counter intake, photos, customer matched' },
  { label: 'Awaiting go-ahead', note: 'Quote texted, waiting on approval' },
  { label: 'In progress', note: 'On the bench, parts logged' },
  { label: 'Ready for pickup', note: 'Pickup SMS sent automatically' },
  { label: 'Invoiced', note: 'Paid, closed, in this month’s report' },
]

type TradeKey = 'watch' | 'shoe' | 'key'

const TRADE_TABS: { key: TradeKey; label: string; Icon: typeof Wrench }[] = [
  { key: 'watch', label: 'Watch', Icon: Wrench },
  { key: 'shoe', label: 'Shoe', Icon: Scissors },
  { key: 'key', label: 'Keys', Icon: KeyRound },
]

const TRADES: Record<TradeKey, {
  kicker: string; title: string; body: string; bullets: string[]
  panelLabel: string; rows: { title: string; meta: string; value: string }[]
}> = {
  watch: {
    kicker: 'Watch repairs',
    title: 'Movements, batteries, pressure tests.',
    body: 'Track a service from intake photos through to water-resistance certification, with the movement, case and bracelet all on one ticket.',
    bullets: [
      'Battery, movement service and full overhaul templates',
      'Pressure test results stored against the job',
      'Parts on order flagged so nothing stalls silently',
      'Turnaround clock per job, visible on the queue',
    ],
    panelLabel: 'Watch bench · today',
    rows: [
      { title: 'Rolex Datejust — full service', meta: 'J. Smith · 5d in shop', value: 'A$465' },
      { title: 'Seiko SNK809 — battery + test', meta: 'M. Patel · awaiting go-ahead', value: 'A$45' },
      { title: 'Omega Speedmaster — gaskets', meta: 'A. Williams · ready', value: 'A$280' },
      { title: 'Tissot PRX — bracelet resize', meta: 'K. Doan · booked in', value: 'A$35' },
    ],
  },
  shoe: {
    kicker: 'Shoe repairs',
    title: 'Soles, heels, stitching, cleaning.',
    body: 'Multi-pair intake with combo pricing, so a customer dropping three pairs becomes one ticket and one clear price — not three guesses.',
    bullets: [
      'Multi-pair intake on a single ticket',
      'Combo pricing and guarantee terms built in',
      'Catalogue keeps naming and pricing consistent',
      'Before photos attached at the counter',
    ],
    panelLabel: 'Shoe bench · today',
    rows: [
      { title: 'Nike Air Max — resole', meta: 'T. Nguyen · 3d in shop', value: 'A$120' },
      { title: '2 pairs — heel tips + clean', meta: 'R. Kaur · combo price', value: 'A$85' },
      { title: 'RM Williams — full resole', meta: 'D. Boyd · in progress', value: 'A$195' },
      { title: 'Blundstones — stitch repair', meta: 'L. Ferrari · ready', value: 'A$60' },
    ],
  },
  key: {
    kicker: 'Mobile services',
    title: 'Auto keys, cutting, callouts.',
    body: 'Quote from the pricing catalogue on the spot, mark whether the callout is included, and invoice before you leave the driveway.',
    bullets: [
      'Pricing catalogue with retail and B2B tiers',
      'Callout-inclusive or added, per job',
      'Suggested quote from job type and quantity',
      'Invoice and take payment on the phone',
    ],
    panelLabel: 'Mobile jobs · today',
    rows: [
      { title: 'BMW 3 Series — key duplication', meta: 'S. Lee · callout incl.', value: 'A$310' },
      { title: 'Hilux — remote programming', meta: 'Fleet: Corio Plumbing', value: 'A$240' },
      { title: 'House rekey — 4 barrels', meta: 'B. Marsh · on site', value: 'A$180' },
      { title: 'Transponder cut — Mazda 3', meta: 'C. Ellis · invoiced', value: 'A$165' },
    ],
  },
}

type TourKey = 'jobs' | 'quote' | 'reports'

const TOURS: Record<TourKey, { label: string; path: string; title: string; body: string }> = {
  jobs: { label: 'Job workflow', path: '/watch-repairs', title: 'The queue is the shop.', body: 'One table per service line, filtered by status and sorted by how long the job has been sitting. Everything one click from the ticket.' },
  quote: { label: 'Quote approval', path: '/quote/8f21c4', title: 'Customers approve in one tap.', body: 'Send a token-linked quote by SMS. They see the line items, approve, and the job moves itself to in progress.' },
  reports: { label: 'Reports', path: '/reports', title: 'Billed, recovered, still to chase.', body: 'Revenue, gross profit and outstanding work value by service line — so you know which bench is actually paying.' },
}

const QUOTE_LINES = [
  { label: 'Full movement service', note: 'Strip, clean, lubricate, regulate', price: 'A$320.00' },
  { label: 'Gasket set replacement', note: 'Case back, crown, crystal', price: 'A$65.00' },
  { label: 'Water-resistance test', note: 'Certified to 100m', price: 'A$45.00' },
  { label: 'Case and bracelet refinish', note: 'Light polish, brushed finish kept', price: 'A$35.00' },
]

const REPORT_CARDS = [
  { label: 'Billed total', value: 'A$64,200', helper: 'last 6 months' },
  { label: 'Revenue received', value: 'A$48,200', helper: '75% recovered' },
  { label: 'Outstanding', value: 'A$16,000', helper: '11 open invoices' },
  { label: 'Gross margin', value: '65%', helper: 'after parts' },
]

const CHART_BARS = [
  { label: 'Feb', h1: 54, h2: 34, h3: 20 },
  { label: 'Mar', h1: 68, h2: 38, h3: 22 },
  { label: 'Apr', h1: 62, h2: 50, h3: 24 },
  { label: 'May', h1: 84, h2: 46, h3: 28 },
  { label: 'Jun', h1: 100, h2: 52, h3: 26 },
  { label: 'Jul', h1: 116, h2: 58, h3: 32 },
]

const TRADE_BLOCKS = [
  {
    title: 'Watch repairs',
    body: 'Movement services, batteries, pressure testing, and full servicing.',
    items: [
      { label: 'Intake', value: 'Case, movement, bracelet' },
      { label: 'Testing', value: 'Pressure result on ticket' },
      { label: 'Parts', value: 'On-order flags' },
      { label: 'Turnaround', value: 'Clock per job' },
    ],
  },
  {
    title: 'Shoe repairs',
    body: 'Soles, heels, stitching, cleaning, and more. Multi-pair intake with combo pricing.',
    items: [
      { label: 'Intake', value: 'Multi-pair, one ticket' },
      { label: 'Pricing', value: 'Combos + guarantee' },
      { label: 'Catalogue', value: 'Consistent naming' },
      { label: 'Evidence', value: 'Before photos' },
    ],
  },
  {
    title: 'Mobile services',
    body: 'Auto keys, cutting and programming, with callouts priced on the spot.',
    items: [
      { label: 'Pricing', value: 'Retail + B2B tiers' },
      { label: 'Callout', value: 'Included or added' },
      { label: 'Quoting', value: 'Suggested totals' },
      { label: 'Payment', value: 'Invoice on site' },
    ],
  },
]

const MOBILE_CHIPS = ['Install as an app', 'Works on tablet', 'Photos from the camera', 'SMS built in']

const PHONE_JOBS = [
  { type: 'Watch repair', title: 'Rolex Datejust — service', status: 'In progress', dot: DOTS.progress },
  { type: 'Shoe repair', title: 'Air Max — resole', status: 'Ready', dot: DOTS.done },
  { type: 'Mobile services', title: 'BMW 3 Series — key', status: 'Awaiting', dot: DOTS.wait },
  { type: 'Watch repair', title: 'Seiko SNK809 — battery', status: 'Booked in', dot: DOTS.neutral },
]

const PRICE_TABLE = [
  { plan: 'Basic · one service tab', detail: 'Watch, shoe or mobile services', price: 'A$25/mo' },
  { plan: 'Basic · two tabs', detail: 'Any two service lines', price: 'A$35/mo' },
  { plan: 'Basic · three tabs', detail: 'All service lines, Basic features', price: 'A$45/mo' },
  { plan: 'Pro · full access', detail: 'All tabs, customer accounts, multi-site', price: 'A$50/mo' },
  { plan: 'Extra shop location', detail: 'Per additional site', price: '+A$25/mo' },
]

const PRICING_NOTES = [
  'Customers, invoicing and reports on every plan',
  '14-day trial, no credit card, cancel any time',
  'Same app on desktop, tablet and phone',
]

const FAQS = [
  { q: 'Do I have to pay for trades I don’t do?', a: 'No. Basic starts at A$25/month with one service tab. Add a second or third tab for A$10/month each, or move to Pro at A$50/month once you want the lot.' },
  { q: 'Can I use it on the shop tablet and my phone?', a: 'Yes. Mainspring installs as an app on iOS and Android as well as running in the browser — same account, same data everywhere.' },
  { q: 'What happens to my open jobs when I switch?', a: 'Most shops enter open jobs as they come back in, which takes a week or two. Keep your diary alongside until you are comfortable.' },
  { q: 'Do customers get texted automatically?', a: 'Quote and pickup messages are sent from the ticket, so the customer hears from you at each status change without anyone remembering to call.' },
]

/* ─── Scroll-reveal wrapper ───────────────────────────────────────────────
 * IntersectionObserver-driven, honours prefers-reduced-motion, and fails
 * open (never leaves content stuck at opacity 0) via both a safety timeout
 * and a graceful degrade when IntersectionObserver is unavailable. */

function Reveal({ children, className = '', id }: { children: React.ReactNode; className?: string; id?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (typeof IntersectionObserver === 'undefined') {
      setShown(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShown(true)
            observer.disconnect()
          }
        }
      },
      { threshold: 0.06, rootMargin: '0px 0px -6% 0px' },
    )
    observer.observe(el)
    // Fail open: never leave the section invisible if the observer never fires.
    const safety = setTimeout(() => setShown(true), 1200)
    return () => {
      observer.disconnect()
      clearTimeout(safety)
    }
  }, [])

  return (
    <div id={id} ref={ref} className={`mkt-reveal ${shown ? 'mkt-shown' : ''} ${className}`}>
      {children}
    </div>
  )
}

/* ─── Small shared bits ─────────────────────────────────────────────────── */

function Container({ children, className = '', style, id }: { children: React.ReactNode; className?: string; style?: React.CSSProperties; id?: string }) {
  return (
    <div id={id} className={`mx-auto w-full ${className}`} style={{ maxWidth: 1320, padding: '0 20px', ...style }}>
      {children}
    </div>
  )
}

function EyebrowVermilion({ children, tracking = '0.28em' }: { children: React.ReactNode; tracking?: string }) {
  return (
    <p style={{ margin: 0, fontSize: 11, fontWeight: 700, letterSpacing: tracking, textTransform: 'uppercase', color: MKT.vermilionDeep }}>
      {children}
    </p>
  )
}

function StatusDot({ color, pulse = false, size = 8 }: { color: string; pulse?: boolean; size?: number }) {
  return (
    <span
      aria-hidden
      className={pulse ? 'mkt-pulse-dot' : undefined}
      style={{ width: size, height: size, background: color, display: 'inline-block', flexShrink: 0 }}
    />
  )
}

const JOB_TABLE_GRID = '52px 1fr 130px 150px 80px'

function JobRow({ job }: { job: (typeof JOB_LIST)[number] }) {
  return (
    <div className="mkt-row-hover" style={{ padding: '13px 18px', borderBottom: `1px solid ${MKT.ruleLight}` }}>
      {/* Mobile — card per row, five columns don't fit narrow screens. */}
      <div className="flex flex-col gap-1.5 sm:hidden">
        <div className="flex items-baseline justify-between gap-3">
          <span style={{ fontSize: 13, color: MKT.ink }}>{job.title}</span>
          <span style={{ fontSize: 13, fontWeight: 700, color: MKT.ink, whiteSpace: 'nowrap' }}>{job.value}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span style={{ fontSize: 11, color: MKT.textBody }}>#{job.number} · {job.customer}</span>
          <span className="inline-flex items-center gap-1.5 whitespace-nowrap" style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: MKT.ink }}>
            <StatusDot color={DOTS[job.tone]} size={7} />
            {job.status}
          </span>
        </div>
      </div>
      {/* Desktop — full five-column row. */}
      <div className="hidden sm:grid items-center" style={{ gridTemplateColumns: JOB_TABLE_GRID, columnGap: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: MKT.textMuted }}>{job.number}</span>
        <span style={{ fontSize: 13, color: MKT.ink }}>{job.title}</span>
        <span style={{ fontSize: 12, color: MKT.textBody }}>{job.customer}</span>
        <span className="inline-flex items-center gap-2" style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: MKT.ink }}>
          <StatusDot color={DOTS[job.tone]} />
          {job.status}
        </span>
        <span style={{ fontSize: 13, fontWeight: 700, color: MKT.ink, textAlign: 'right' }}>{job.value}</span>
      </div>
    </div>
  )
}

function JobTableHeader() {
  return (
    <div
      className="hidden sm:grid"
      style={{ gridTemplateColumns: JOB_TABLE_GRID, padding: '11px 18px', borderBottom: `1px solid ${MKT.ink}`, columnGap: 8 }}
    >
      {JOBS_COLS.map((c) => (
        <span key={c} style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted }}>
          {c}
        </span>
      ))}
    </div>
  )
}

/* ─── Accessible tab group with arrow-key navigation ───────────────────── */

function useTabKeyNav<T extends string>(keys: readonly T[], onSelect: (k: T) => void) {
  const refs = useRef<Array<HTMLButtonElement | null>>([])
  const onKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next = -1
    if (e.key === 'ArrowRight') next = (index + 1) % keys.length
    else if (e.key === 'ArrowLeft') next = (index - 1 + keys.length) % keys.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = keys.length - 1
    if (next >= 0) {
      e.preventDefault()
      onSelect(keys[next])
      refs.current[next]?.focus()
    }
  }
  return { refs, onKeyDown }
}

/* ═══════════════════════════════════════════════════════════════════════
 * Sections
 * ═══════════════════════════════════════════════════════════════════════ */

function Nav() {
  return (
    <div style={{ borderBottom: `2px solid ${MKT.ink}`, background: MKT.paper }}>
      <Container className="flex items-center justify-between" style={{ padding: '18px 20px' }}>
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <img src="/marketing/mainspring-badge-vermilion.svg" alt="" style={{ width: 34, height: 34, display: 'block' }} />
          <span className="mkt-serif hidden min-[420px]:inline" style={{ fontSize: 21, fontWeight: 700, letterSpacing: '-0.01em', color: MKT.ink }}>Mainspring</span>
        </div>
        <nav className="flex items-center gap-3 lg:gap-[30px] shrink-0">
          <a href="#product" className="hidden lg:inline" style={{ fontSize: 13, fontWeight: 600, color: MKT.ink }}>Product</a>
          <a href="#trades" className="hidden lg:inline" style={{ fontSize: 13, fontWeight: 600, color: MKT.ink }}>Trades</a>
          <a href="#pricing" className="hidden sm:inline" style={{ fontSize: 13, fontWeight: 600, color: MKT.ink }}>Pricing</a>
          <a href="#faq" className="hidden lg:inline" style={{ fontSize: 13, fontWeight: 600, color: MKT.ink }}>FAQ</a>
          <Link to="/login" className="hidden sm:inline" style={{ fontSize: 13, fontWeight: 600, color: MKT.ink }}>Log in</Link>
          <Link
            to="/signup"
            className="mkt-nav-cta inline-flex items-center whitespace-nowrap px-3 sm:px-4"
            style={{ height: 42, fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}
          >
            Start your shop
          </Link>
        </nav>
      </Container>
    </div>
  )
}

function Hero() {
  return (
    <div style={{ background: MKT.oatmeal }}>
      <Reveal>
        <Container style={{ padding: '48px 20px 0' }}>
          <EyebrowVermilion tracking="0.3em">Watches · Shoes · Keys</EyebrowVermilion>
          <h1
            style={{
              margin: '18px 0 0',
              fontSize: 'clamp(44px, 8.5vw, 116px)',
              lineHeight: 0.88,
              fontWeight: 800,
              letterSpacing: '-0.06em',
              color: MKT.ink,
            }}
          >
            All your repairs.<br />One place.
          </h1>
          <div className="grid grid-cols-1 lg:grid-cols-[1.05fr_0.95fr_0.9fr] gap-8" style={{ marginTop: 36, paddingBottom: 40 }}>
            <p style={{ margin: 0, fontSize: 16, lineHeight: 1.6, color: MKT.textBody }}>
              Intake, quotes, approvals, invoices and reports for every trade you run — one ticket book instead of a diary, a notebook and three spreadsheets.
            </p>
            <div className="flex items-start flex-wrap">
              <Link
                to="/signup"
                className="mkt-btn-primary inline-flex items-center whitespace-nowrap"
                style={{ height: 54, padding: '0 26px', fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase' }}
              >
                Start your shop
              </Link>
              <a
                href="#product"
                className="mkt-btn-outline-ink inline-flex items-center whitespace-nowrap"
                style={{ height: 54, padding: '0 26px', fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase' }}
              >
                Demo shop
              </a>
            </div>
            <div style={{ borderLeft: `1px solid #CFC6B4`, paddingLeft: 22 }}>
              <p style={{ margin: 0, fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#5E574D' }}>From</p>
              <p style={{ margin: '8px 0 0', fontSize: 34, fontWeight: 800, letterSpacing: '-0.045em', color: MKT.ink, lineHeight: 1 }}>
                A$25<span style={{ fontSize: 15, fontWeight: 600, color: '#5E574D' }}>/mo</span>
              </p>
              <p style={{ margin: '8px 0 0', fontSize: 12, lineHeight: 1.5, color: MKT.textBody }}>
                14-day trial · no card required
              </p>
            </div>
          </div>
        </Container>
      </Reveal>

      <Reveal>
        <Container id="product" style={{ padding: '0 20px 40px' }}>
          <div style={{ background: MKT.paper, border: `1px solid ${MKT.ink}` }}>
            <div className="flex items-center justify-between" style={{ padding: '15px 18px', borderBottom: `1px solid ${MKT.ink}` }}>
              <span style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-0.025em', color: MKT.ink }}>Live service queue</span>
              <span className="hidden sm:inline" style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted }}>
                app.mainspring.au / dashboard
              </span>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4" style={{ borderBottom: `1px solid ${MKT.ink}` }}>
              {STAT_CARDS.map((card) => (
                <div key={card.label} style={{ padding: 18, borderLeft: `1px solid ${MKT.ruleMid}` }}>
                  <p style={{ margin: 0, fontSize: 9, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted }}>{card.label}</p>
                  <p style={{ margin: '10px 0 0', fontSize: 28, fontWeight: 800, letterSpacing: '-0.05em', color: MKT.ink, lineHeight: 1 }}>{card.value}</p>
                  {card.helper && <p style={{ margin: '6px 0 0', fontSize: 11, color: MKT.textBody }}>{card.helper}</p>}
                </div>
              ))}
            </div>
            <JobTableHeader />
            {JOB_LIST.map((job) => <JobRow key={job.number} job={job} />)}
          </div>
        </Container>
      </Reveal>
    </div>
  )
}

function FlowStrip() {
  return (
    <Reveal className="block" id="flow">
      <div style={{ borderBottom: `1px solid ${MKT.ink}` }}>
        <Container>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            {LEDGER.map((l) => (
              <div key={l.n} style={{ padding: '30px 22px 34px', borderLeft: `1px solid ${MKT.ruleMid}`, borderTop: `1px solid ${MKT.ruleMid}` }}>
                <p style={{ margin: 0, fontSize: 'clamp(36px, 5vw, 56px)', fontWeight: 800, letterSpacing: '-0.055em', color: MKT.vermilion, lineHeight: 0.88 }}>{l.n}</p>
                <p style={{ margin: '14px 0 0', fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.ink }}>{l.label}</p>
                <p style={{ margin: '10px 0 0', fontSize: 13, lineHeight: 1.6, color: MKT.textBody }}>{l.body}</p>
              </div>
            ))}
          </div>
        </Container>
      </div>
    </Reveal>
  )
}

function Lifecycle({ step }: { step: number }) {
  return (
    <Reveal>
      <div style={{ borderBottom: `1px solid ${MKT.ink}` }}>
        <Container style={{ padding: '48px 20px 52px' }}>
          <div className="flex items-end justify-between gap-8 flex-wrap">
            <h2 style={{ margin: 0, maxWidth: 620, fontSize: 'clamp(30px, 4.4vw, 46px)', lineHeight: 1.0, fontWeight: 800, letterSpacing: '-0.05em', color: MKT.ink }}>
              The job moves. You don&rsquo;t chase it.
            </h2>
            <p style={{ margin: 0, maxWidth: 380, fontSize: 15, lineHeight: 1.6, color: MKT.textBody }}>
              Every status change texts the customer, updates the queue and lands in reports. No double entry, no phone tag.
            </p>
          </div>
          <div style={{ marginTop: 26, border: `1px solid ${MKT.ink}` }}>
            <div className="flex items-center justify-between" style={{ padding: '16px 20px', borderBottom: `1px solid ${MKT.ink}` }}>
              <div>
                <p style={{ margin: 0, fontSize: 10, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted }}>Job ticket #00142</p>
                <p style={{ margin: '6px 0 0', fontSize: 16, fontWeight: 700, letterSpacing: '-0.02em', color: MKT.ink }}>Rolex Datejust — full service</p>
              </div>
              <span
                aria-live="polite"
                className="inline-flex items-center whitespace-nowrap"
                style={{ gap: 9, fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: MKT.ink }}
              >
                <StatusDot color={MKT.vermilion} size={9} pulse />
                {LIFECYCLE[step].label}
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
              {LIFECYCLE.map((s, i) => {
                const active = i === step
                const past = i < step
                return (
                  <div
                    key={s.label}
                    style={{
                      padding: '20px 18px 24px',
                      borderLeft: `1px solid ${MKT.ruleMid}`,
                      borderTop: `1px solid ${MKT.ruleMid}`,
                      background: active ? 'rgba(10,10,10,0.05)' : 'transparent',
                      transition: 'background 240ms ease',
                    }}
                  >
                    <div className="flex items-center" style={{ gap: 9 }}>
                      <StatusDot color={active ? MKT.vermilion : past ? MKT.ink : MKT.greyChip} />
                      <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted }}>Step {i + 1}</span>
                    </div>
                    <p style={{ margin: '12px 0 0', fontSize: 15, fontWeight: 700, letterSpacing: '-0.02em', color: active ? MKT.ink : MKT.textBody }}>{s.label}</p>
                    <p style={{ margin: '6px 0 0', fontSize: 12, lineHeight: 1.5, color: active ? MKT.textBody : MKT.textMuted }}>{s.note}</p>
                  </div>
                )
              })}
            </div>
          </div>
        </Container>
      </div>
    </Reveal>
  )
}

function TradeSwitcher({ trade, setTrade }: { trade: TradeKey; setTrade: (t: TradeKey) => void }) {
  const keys = TRADE_TABS.map((t) => t.key)
  const { refs, onKeyDown } = useTabKeyNav(keys, setTrade)
  const active = TRADES[trade]

  return (
    <Reveal id="trades">
      <div style={{ background: MKT.oatmeal }}>
        <Container style={{ padding: '48px 20px 52px' }}>
          <div className="flex items-end justify-between gap-6 flex-wrap">
            <div style={{ maxWidth: 620 }}>
              <EyebrowVermilion>Three benches, one system</EyebrowVermilion>
              <h2 style={{ margin: '14px 0 0', fontSize: 'clamp(30px, 4.4vw, 48px)', lineHeight: 1.0, fontWeight: 800, letterSpacing: '-0.055em', color: MKT.ink }}>
                Built for what you actually repair.
              </h2>
            </div>
            <div role="tablist" aria-label="Trades" className="flex shrink-0" style={{ border: `1px solid ${MKT.ink}` }}>
              {TRADE_TABS.map(({ key, label, Icon }, i) => {
                const isActive = trade === key
                return (
                  <button
                    key={key}
                    ref={(el) => { refs.current[i] = el }}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    tabIndex={isActive ? 0 : -1}
                    onClick={() => setTrade(key)}
                    onKeyDown={(e) => onKeyDown(e, i)}
                    className="mkt-tab inline-flex items-center whitespace-nowrap px-2.5 sm:px-[18px]"
                    style={{
                      gap: 9,
                      height: 46,
                      border: 'none',
                      borderRight: i < TRADE_TABS.length - 1 ? `1px solid ${MKT.ink}` : 'none',
                      cursor: 'pointer',
                      fontFamily: "'Plus Jakarta Sans', sans-serif",
                      fontSize: 11,
                      fontWeight: 700,
                      letterSpacing: '0.14em',
                      textTransform: 'uppercase',
                      background: isActive ? MKT.vermilion : 'transparent',
                      color: isActive ? MKT.ink : MKT.textBody,
                      transition: 'background 160ms ease',
                    }}
                  >
                    <Icon size={15} strokeWidth={1.9} aria-hidden />
                    {label}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2" style={{ marginTop: 28, border: `1px solid ${MKT.ink}`, background: MKT.paper }} role="tabpanel">
            <div style={{ padding: '28px 24px 30px' }}>
              <p style={{ margin: 0, fontSize: 10, fontWeight: 700, letterSpacing: '0.22em', textTransform: 'uppercase', color: MKT.textMuted }}>{active.kicker}</p>
              <h3 style={{ margin: '12px 0 0', fontSize: 26, lineHeight: 1.08, fontWeight: 800, letterSpacing: '-0.04em', color: MKT.ink }}>{active.title}</h3>
              <p style={{ margin: '14px 0 0', fontSize: 15, lineHeight: 1.65, color: MKT.textBody }}>{active.body}</p>
              <div style={{ marginTop: 20 }}>
                {active.bullets.map((b) => (
                  <div key={b} className="flex items-baseline" style={{ gap: 12, padding: '11px 0', borderTop: `1px solid ${MKT.ruleMid}` }}>
                    <span style={{ width: 7, height: 7, background: MKT.vermilion, flexShrink: 0 }} aria-hidden />
                    <span style={{ fontSize: 13, lineHeight: 1.5, color: MKT.ink }}>{b}</span>
                  </div>
                ))}
              </div>
            </div>
            <div
              className="lg:border-l lg:border-[#0A0A0A]"
              style={{ background: MKT.oatmealPanel, borderTop: `1px solid ${MKT.ink}` }}
            >
              <p style={{ margin: 0, padding: '14px 24px', borderBottom: `1px solid ${MKT.ruleMid}`, fontSize: 10, fontWeight: 700, letterSpacing: '0.22em', textTransform: 'uppercase', color: MKT.textMuted }}>
                {active.panelLabel}
              </p>
              {active.rows.map((row) => (
                <div key={row.title} className="flex items-center justify-between gap-4" style={{ padding: '14px 24px', borderBottom: `1px solid ${MKT.ruleLight}` }}>
                  <div>
                    <p style={{ margin: 0, fontSize: 13, color: MKT.ink }}>{row.title}</p>
                    <p style={{ margin: '4px 0 0', fontSize: 11, color: MKT.textMuted }}>{row.meta}</p>
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 700, color: MKT.vermilionDeep, whiteSpace: 'nowrap' }}>{row.value}</span>
                </div>
              ))}
            </div>
          </div>
        </Container>
      </div>
    </Reveal>
  )
}

function ProductTour({ tour, setTour }: { tour: TourKey; setTour: (t: TourKey) => void }) {
  const keys = Object.keys(TOURS) as TourKey[]
  const { refs, onKeyDown } = useTabKeyNav(keys, setTour)
  const def = TOURS[tour]

  return (
    <Reveal>
      <div style={{ borderBottom: `1px solid ${MKT.ink}` }}>
        <Container style={{ padding: '48px 20px 52px' }}>
          <div className="flex items-end justify-between gap-6 flex-wrap">
            <div style={{ maxWidth: 620 }}>
              <EyebrowVermilion>Product tour</EyebrowVermilion>
              <h2 style={{ margin: '14px 0 0', fontSize: 'clamp(28px, 4vw, 44px)', lineHeight: 1.0, fontWeight: 800, letterSpacing: '-0.05em', color: MKT.ink }}>{def.title}</h2>
              <p style={{ margin: '12px 0 0', maxWidth: 520, fontSize: 15, lineHeight: 1.6, color: MKT.textBody }}>{def.body}</p>
            </div>
            <div role="tablist" aria-label="Product tour" className="flex shrink-0" style={{ border: `1px solid ${MKT.ink}` }}>
              {keys.map((k, i) => {
                const isActive = tour === k
                return (
                  <button
                    key={k}
                    ref={(el) => { refs.current[i] = el }}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    tabIndex={isActive ? 0 : -1}
                    onClick={() => setTour(k)}
                    onKeyDown={(e) => onKeyDown(e, i)}
                    className="mkt-tab whitespace-nowrap px-1.5 sm:px-[18px] text-[9px] sm:text-[11px]"
                    style={{
                      height: 44,
                      border: 'none',
                      borderRight: i < keys.length - 1 ? `1px solid ${MKT.ink}` : 'none',
                      cursor: 'pointer',
                      fontFamily: "'Plus Jakarta Sans', sans-serif",
                      fontWeight: 700,
                      letterSpacing: '0.14em',
                      textTransform: 'uppercase',
                      background: isActive ? MKT.ink : 'transparent',
                      color: isActive ? MKT.paper : MKT.ink,
                      transition: 'background 160ms ease',
                    }}
                  >
                    {TOURS[k].label}
                  </button>
                )
              })}
            </div>
          </div>

          <div style={{ marginTop: 26, border: `1px solid ${MKT.ink}` }}>
            <div className="flex items-center justify-between" style={{ padding: '12px 18px', borderBottom: `1px solid ${MKT.ink}` }}>
              <span className="truncate" style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted }}>
                app.mainspring.au{def.path}
              </span>
              <span className="flex shrink-0" style={{ gap: 6 }} aria-hidden>
                <span style={{ width: 9, height: 9, background: MKT.vermilion }} />
                <span style={{ width: 9, height: 9, background: MKT.ruleMid }} />
                <span style={{ width: 9, height: 9, background: MKT.ruleMid }} />
              </span>
            </div>
            <div role="tabpanel" style={{ minHeight: 380, background: MKT.paper }}>
              {tour === 'jobs' && (
                <div>
                  <div className="flex items-start justify-between gap-4 flex-wrap" style={{ padding: '20px 20px', borderBottom: `1px solid ${MKT.ink}` }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: 20, fontWeight: 800, letterSpacing: '-0.035em', color: MKT.ink }}>Watch Repairs</h3>
                      <p style={{ margin: '5px 0 0', fontSize: 12, color: MKT.textMuted }}>Movement services, batteries, pressure testing, and full servicing.</p>
                    </div>
                    <span className="inline-flex items-center whitespace-nowrap" style={{ height: 36, padding: '0 16px', background: MKT.ink, color: MKT.paper, fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                      New job ticket
                    </span>
                  </div>
                  <JobTableHeader />
                  {JOB_LIST.map((job) => <JobRow key={job.number} job={job} />)}
                </div>
              )}
              {tour === 'quote' && (
                <div className="grid grid-cols-1 lg:grid-cols-2">
                  <div style={{ padding: '26px 24px', borderBottom: `1px solid ${MKT.ink}` }} className="lg:border-b-0 lg:border-r lg:border-[#0A0A0A]">
                    <p style={{ margin: 0, fontSize: 10, fontWeight: 700, letterSpacing: '0.22em', textTransform: 'uppercase', color: MKT.textMuted }}>Quote for approval · #00142</p>
                    <h3 style={{ margin: '12px 0 0', fontSize: 24, lineHeight: 1.1, fontWeight: 800, letterSpacing: '-0.04em', color: MKT.ink }}>Rolex Datejust — full service</h3>
                    <p style={{ margin: '8px 0 0', fontSize: 13, color: MKT.textBody }}>Prepared by Geelong bench · valid 14 days</p>
                    <div style={{ marginTop: 18 }}>
                      {QUOTE_LINES.map((l) => (
                        <div key={l.label} className="flex items-baseline justify-between gap-4" style={{ padding: '12px 0', borderTop: `1px solid ${MKT.ruleMid}` }}>
                          <div>
                            <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: MKT.ink }}>{l.label}</p>
                            <p style={{ margin: '3px 0 0', fontSize: 11, color: MKT.textMuted }}>{l.note}</p>
                          </div>
                          <span style={{ fontSize: 13, fontWeight: 700, color: MKT.ink, whiteSpace: 'nowrap' }}>{l.price}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col justify-center" style={{ padding: '26px 24px', background: MKT.oatmeal }}>
                    <p style={{ margin: 0, fontSize: 10, fontWeight: 700, letterSpacing: '0.22em', textTransform: 'uppercase', color: MKT.textMuted }}>Total incl. GST</p>
                    <p style={{ margin: '10px 0 0', fontSize: 'clamp(44px, 6vw, 76px)', fontWeight: 800, letterSpacing: '-0.06em', color: MKT.ink, lineHeight: 0.9 }}>A$465</p>
                    <p style={{ margin: '16px 0 0', maxWidth: 340, fontSize: 14, lineHeight: 1.6, color: MKT.textBody }}>
                      Sent by SMS as a token link. The customer taps approve and the job moves itself onto the bench.
                    </p>
                    <div className="flex flex-wrap" style={{ marginTop: 22 }}>
                      <span className="inline-flex items-center whitespace-nowrap" style={{ height: 44, padding: '0 20px', background: MKT.vermilion, color: MKT.ink, fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
                        Approve &amp; start work
                      </span>
                      <span className="inline-flex items-center whitespace-nowrap" style={{ height: 44, padding: '0 20px', border: `1px solid ${MKT.ink}`, color: MKT.ink, fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
                        Ask a question
                      </span>
                    </div>
                  </div>
                </div>
              )}
              {tour === 'reports' && (
                <div>
                  <div className="grid grid-cols-2 lg:grid-cols-4" style={{ borderBottom: `1px solid ${MKT.ink}` }}>
                    {REPORT_CARDS.map((rc) => (
                      <div key={rc.label} style={{ padding: 18, borderLeft: `1px solid ${MKT.ruleMid}` }}>
                        <p style={{ margin: 0, fontSize: 9, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted }}>{rc.label}</p>
                        <p style={{ margin: '10px 0 0', fontSize: 26, fontWeight: 800, letterSpacing: '-0.05em', color: MKT.ink, lineHeight: 1 }}>{rc.value}</p>
                        <p style={{ margin: '6px 0 0', fontSize: 11, color: MKT.textBody }}>{rc.helper}</p>
                      </div>
                    ))}
                  </div>
                  <div style={{ padding: '22px 20px 26px' }}>
                    <p style={{ margin: '0 0 18px', fontSize: 11, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted }}>
                      Revenue by service line · last 6 months
                    </p>
                    <div className="flex items-end" style={{ gap: 12, height: 200 }}>
                      {CHART_BARS.map((bar) => (
                        <div key={bar.label} className="flex flex-col items-stretch justify-end" style={{ flex: 1, gap: 8, height: '100%' }}>
                          <div className="flex flex-col">
                            <div style={{ height: bar.h1, background: MKT.vermilion }} />
                            <div style={{ height: bar.h2, background: MKT.ink }} />
                            <div style={{ height: bar.h3, background: MKT.greyChip }} />
                          </div>
                          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.textMuted, textAlign: 'center' }}>{bar.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Container>
      </div>
    </Reveal>
  )
}

function TradeColumns() {
  return (
    <Reveal>
      <div style={{ borderBottom: `1px solid ${MKT.ink}` }}>
        <Container>
          <div className="grid grid-cols-1 sm:grid-cols-3">
            {TRADE_BLOCKS.map((t) => (
              <div key={t.title} style={{ padding: '30px 22px 32px', borderLeft: `1px solid ${MKT.ruleMid}`, borderTop: `1px solid ${MKT.ruleMid}` }}>
                <h3 style={{ margin: 0, fontSize: 24, fontWeight: 800, letterSpacing: '-0.045em', color: MKT.ink }}>{t.title}</h3>
                <p style={{ margin: '12px 0 0', fontSize: 14, lineHeight: 1.6, color: MKT.textBody }}>{t.body}</p>
                <div style={{ marginTop: 16 }}>
                  {t.items.map((it) => (
                    <div key={it.label} className="flex items-baseline justify-between gap-3" style={{ padding: '10px 0', borderTop: `1px solid ${MKT.ruleLight}` }}>
                      <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: MKT.textMuted }}>{it.label}</span>
                      <span style={{ fontSize: 12, color: MKT.ink, textAlign: 'right' }}>{it.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Container>
      </div>
    </Reveal>
  )
}

function MobileBlock() {
  return (
    <Reveal>
      <div style={{ borderBottom: `1px solid ${MKT.ink}` }}>
        <Container className="grid grid-cols-1 lg:grid-cols-[1fr_340px]">
          <div style={{ padding: '44px 20px 46px' }}>
            <EyebrowVermilion>On the counter, on the road</EyebrowVermilion>
            <h2 style={{ margin: '14px 0 0', fontSize: 'clamp(30px, 4.4vw, 46px)', lineHeight: 1.0, fontWeight: 800, letterSpacing: '-0.05em', color: MKT.ink }}>
              Take intake anywhere.
            </h2>
            <p style={{ margin: '16px 0 0', maxWidth: 520, fontSize: 15, lineHeight: 1.65, color: MKT.textBody }}>
              Install Mainspring on the shop tablet or your phone. Book a job at the counter, cut a key at the customer&rsquo;s car, photograph a sole before you start — same ticket, same second.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2" style={{ columnGap: 24, marginTop: 22, maxWidth: 460 }}>
              {MOBILE_CHIPS.map((chip) => (
                <div key={chip} className="flex items-baseline" style={{ gap: 10, padding: '11px 0', borderTop: `1px solid ${MKT.ruleMid}` }}>
                  <span style={{ width: 6, height: 6, background: MKT.vermilion, flexShrink: 0 }} aria-hidden />
                  <span style={{ fontSize: 12, fontWeight: 600, color: MKT.ink }}>{chip}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ borderTop: `1px solid ${MKT.ruleMid}`, padding: '32px 20px' }} className="lg:border-t-0 lg:border-l lg:border-[#D8D6CE]">
            <div style={{ width: 258, maxWidth: '100%', background: MKT.ink, padding: 9, margin: '0 auto' }}>
              <div style={{ background: MKT.paper }}>
                <div className="flex items-center justify-between" style={{ padding: '9px 14px', borderBottom: `1px solid ${MKT.ruleMid}`, fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', color: MKT.ink }}>
                  <span>9:41</span>
                  <span>Geelong bench</span>
                </div>
                <div style={{ padding: 14 }}>
                  <p style={{ margin: 0, fontSize: 9, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.textMuted }}>Today</p>
                  <h3 style={{ margin: '6px 0 0', fontSize: 20, lineHeight: 1.05, fontWeight: 800, letterSpacing: '-0.04em', color: MKT.ink }}>6 jobs on<br />the bench</h3>
                  <div style={{ marginTop: 12 }}>
                    {PHONE_JOBS.map((pj) => (
                      <div key={pj.title} style={{ padding: '10px 0', borderTop: `1px solid ${MKT.ruleMid}` }}>
                        <div className="flex items-center justify-between" style={{ gap: 8 }}>
                          <span style={{ fontSize: 8, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: MKT.textMuted }}>{pj.type}</span>
                          <span className="inline-flex items-center" style={{ gap: 6, fontSize: 8, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: MKT.ink }}>
                            <StatusDot color={pj.dot} size={6} />
                            {pj.status}
                          </span>
                        </div>
                        <p style={{ margin: '5px 0 0', fontSize: 12, color: MKT.ink }}>{pj.title}</p>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center justify-center" style={{ height: 44, background: MKT.vermilion, color: MKT.ink, fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', marginTop: 12 }}>
                    New job ticket
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Container>
      </div>
    </Reveal>
  )
}

function Pricing() {
  return (
    <Reveal id="pricing">
      <div style={{ borderBottom: `1px solid ${MKT.ink}` }}>
        <Container className="grid grid-cols-1 lg:grid-cols-[0.9fr_1.1fr]">
          <div style={{ padding: '44px 20px 46px' }}>
            <EyebrowVermilion>Rate card</EyebrowVermilion>
            <h2 style={{ margin: '14px 0 0', fontSize: 'clamp(32px, 5vw, 52px)', lineHeight: 0.98, fontWeight: 800, letterSpacing: '-0.055em', color: MKT.ink }}>
              Pay for the tabs you use.
            </h2>
            <p style={{ margin: '16px 0 0', maxWidth: 380, fontSize: 15, lineHeight: 1.65, color: MKT.textBody }}>
              One price per service line. No seat maths, no annual lock-in, no sales call to find out what it costs.
            </p>
            <div style={{ marginTop: 20 }}>
              {PRICING_NOTES.map((n) => (
                <div key={n} className="flex items-baseline" style={{ gap: 10, padding: '10px 0', borderTop: `1px solid ${MKT.ruleMid}` }}>
                  <span style={{ width: 6, height: 6, background: MKT.ink, flexShrink: 0 }} aria-hidden />
                  <span style={{ fontSize: 13, color: MKT.ink }}>{n}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ borderTop: `1px solid ${MKT.ink}` }} className="lg:border-t-0 lg:border-l lg:border-[#0A0A0A]">
            {PRICE_TABLE.map((p) => (
              <div key={p.plan} className="mkt-row-hover flex items-baseline justify-between gap-4 flex-wrap" style={{ padding: '18px 24px', borderBottom: `1px solid ${MKT.ruleLight}` }}>
                <div>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: MKT.ink }}>{p.plan}</p>
                  <p style={{ margin: '4px 0 0', fontSize: 12, color: MKT.textMuted }}>{p.detail}</p>
                </div>
                <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.045em', color: MKT.ink, whiteSpace: 'nowrap' }}>{p.price}</span>
              </div>
            ))}
            <Link
              to="/signup"
              className="mkt-pricing-cta flex items-center justify-between"
              style={{ padding: '24px 24px', fontSize: 13, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase' }}
            >
              <span>Start your shop — 14-day trial</span><span aria-hidden>&rarr;</span>
            </Link>
          </div>
        </Container>
      </div>
    </Reveal>
  )
}

function Faq() {
  return (
    <Reveal id="faq">
      <div style={{ borderBottom: `1px solid ${MKT.ink}` }}>
        <Container style={{ padding: '44px 20px 46px' }}>
          <h2 style={{ margin: '0 0 24px', fontSize: 'clamp(28px, 3.4vw, 40px)', fontWeight: 800, letterSpacing: '-0.05em', color: MKT.ink }}>Common questions</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2" style={{ columnGap: 48 }}>
            {FAQS.map((f) => (
              <div key={f.q} style={{ padding: '20px 0', borderTop: `1px solid ${MKT.ink}` }}>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, letterSpacing: '-0.02em', color: MKT.ink }}>{f.q}</h3>
                <p style={{ margin: '10px 0 0', fontSize: 13, lineHeight: 1.65, color: MKT.textBody }}>{f.a}</p>
              </div>
            ))}
          </div>
        </Container>
      </div>
    </Reveal>
  )
}

function ClosingCTA() {
  return (
    <Reveal>
      <div style={{ background: MKT.vermilion }}>
        <Container className="flex items-end justify-between gap-8 flex-wrap" style={{ padding: '54px 20px 58px' }}>
          <div style={{ maxWidth: 700 }}>
            <h2 style={{ margin: 0, fontSize: 'clamp(36px, 6vw, 62px)', lineHeight: 0.96, fontWeight: 800, letterSpacing: '-0.06em', color: MKT.white }}>
              Bring your repairs into one spot.
            </h2>
            <p style={{ margin: '16px 0 0', maxWidth: 460, fontSize: 15, lineHeight: 1.65, color: MKT.ink }}>
              Ten minutes to set up your shop. Keep the paper diary for a week if you like — you won&rsquo;t need it.
            </p>
          </div>
          <div className="flex flex-wrap shrink-0">
            <Link to="/signup" className="mkt-btn-close-primary inline-flex items-center whitespace-nowrap px-4 sm:px-[26px]" style={{ height: 56, fontSize: 12, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
              Start your shop
            </Link>
            <a href="#pricing" className="mkt-btn-close-outline inline-flex items-center whitespace-nowrap px-4 sm:px-[26px]" style={{ height: 56, fontSize: 12, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
              Talk to us
            </a>
          </div>
        </Container>
      </div>
    </Reveal>
  )
}

function Footer() {
  return (
    <div style={{ background: MKT.oatmealDeep }}>
      <Container className="flex items-center justify-between gap-5 flex-wrap" style={{ padding: '22px 20px' }}>
        <div className="flex items-center flex-wrap" style={{ gap: 16 }}>
          <img src="/marketing/mainspring-badge-vermilion.svg" alt="" style={{ width: 38, height: 38, display: 'block' }} />
          <span className="mkt-serif" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.01em', color: MKT.ink }}>Mainspring</span>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.textBody }}>© 2026 · mainspring.au</span>
        </div>
        <div className="flex flex-wrap" style={{ gap: 20 }}>
          <a href="#pricing" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.textBody }}>Pricing</a>
          <Link to="/login" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.textBody }}>Log in</Link>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.greyChip }}>Privacy</span>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.greyChip }}>Contact</span>
        </div>
      </Container>
    </div>
  )
}

/* ─── Root export ─── */

const LIFECYCLE_SPEED_MS = 1600

export default function LandingPage() {
  const { token, sessionReady } = useAuth()
  const [trade, setTrade] = useState<TradeKey>('watch')
  const [tour, setTour] = useState<TourKey>('jobs')
  const [step, setStep] = useState(0)

  const reduceMotion = useMemo(
    () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
    [],
  )

  // Always render the landing page in the default (light) theme, ignoring any saved app theme.
  useEffect(() => {
    const saved = document.documentElement.getAttribute('data-theme')
    document.documentElement.removeAttribute('data-theme')
    return () => {
      if (saved) document.documentElement.setAttribute('data-theme', saved)
      else document.documentElement.removeAttribute('data-theme')
    }
  }, [])

  useEffect(() => {
    if (reduceMotion) return
    const id = setInterval(() => setStep((s) => (s + 1) % LIFECYCLE.length), LIFECYCLE_SPEED_MS)
    return () => clearInterval(id)
  }, [reduceMotion])

  // After /auth/session succeeds, send signed-in users straight to the app.
  if (token && sessionReady) return <Navigate to="/dashboard" replace />

  return (
    <div className="mkt-landing min-h-screen">
      <style>{MARKETING_CSS}</style>
      <Nav />
      <Hero />
      <FlowStrip />
      <Lifecycle step={step} />
      <TradeSwitcher trade={trade} setTrade={setTrade} />
      <ProductTour tour={tour} setTour={setTour} />
      <TradeColumns />
      <MobileBlock />
      <Pricing />
      <Faq />
      <ClosingCTA />
      <Footer />
    </div>
  )
}
