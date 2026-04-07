import { Navigate, Link } from 'react-router-dom'
import {
  Wrench,
  Scissors,
  KeyRound,
  CheckCircle2,
  ClipboardCheck,
  Receipt,
  Users,
  BarChart3,
  ArrowRight,
  PackageOpen,
  Sparkles,
  MapPin,
  ShoppingCart,
  Plus,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

const LANDING_CSS = `
@keyframes lpFadeUp {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes lpPulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
@keyframes lpFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}
.lp-reveal {
  opacity: 0;
  animation: lpFadeUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
.lp-reveal-delay-1 { animation-delay: 0.08s; }
.lp-reveal-delay-2 { animation-delay: 0.16s; }
.lp-reveal-delay-3 { animation-delay: 0.24s; }
.lp-reveal-delay-4 { animation-delay: 0.32s; }
.lp-reveal-delay-5 { animation-delay: 0.40s; }
.lp-reveal-delay-6 { animation-delay: 0.48s; }
.lp-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.lp-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 14px rgba(90, 55, 16, 0.08), 0 18px 34px rgba(90, 55, 16, 0.10);
}
.lp-btn {
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}
.lp-btn:hover {
  transform: translateY(-2px);
}
.lp-kanban-card {
  background: #FFFDF9;
  border: 1px solid #EDE4D7;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
}
.lp-kanban-card:last-child {
  margin-bottom: 0;
}
`

/* ─── Kanban preview ─── */

const KANBAN_COLUMNS: { label: string; color: string; dot: string; cards: string[] }[] = [
  {
    label: 'Awaiting Quote',
    color: '#FDF3E0',
    dot: '#D4A017',
    cards: ['Sarah - Omega Seamaster', '3x Keys - Fleet'],
  },
  {
    label: 'Go Ahead',
    color: '#EAF4EC',
    dot: '#3A9E5F',
    cards: ['John - Toyota Hilux', 'Mike - Chelsea Boots'],
  },
  {
    label: 'Working On',
    color: '#EEF2FD',
    dot: '#4B72E0',
    cards: ['Anna - Rolex Datejust'],
  },
  {
    label: 'Completed',
    color: '#F3F0FF',
    dot: '#7C5CBF',
    cards: ['Dan - Heel Repair', 'Sue - Key Cut x2'],
  },
]

function KanbanPreview() {
  return (
    <div
      className="lp-reveal lp-reveal-delay-1"
      style={{ display: 'flex', flexDirection: 'column', gap: 0 }}
    >
      <div
        style={{
          backgroundColor: 'var(--cafe-surface)',
          border: '1px solid #E0D5C6',
          borderRadius: 20,
          boxShadow: '0 2px 8px rgba(90,55,16,0.07), 0 20px 48px rgba(90,55,16,0.12)',
          overflow: 'hidden',
        }}
      >
        {/* Mock window chrome */}
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid #EBE2D6',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            backgroundColor: '#F7F2EB',
          }}
        >
          <span style={{ width: 10, height: 10, borderRadius: 99, backgroundColor: '#E8796A', display: 'inline-block' }} />
          <span style={{ width: 10, height: 10, borderRadius: 99, backgroundColor: '#F0B34A', display: 'inline-block' }} />
          <span style={{ width: 10, height: 10, borderRadius: 99, backgroundColor: '#5DBD72', display: 'inline-block' }} />
          <span
            style={{
              marginLeft: 12,
              fontSize: '0.7rem',
              fontWeight: 600,
              color: 'var(--cafe-text-muted)',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
            }}
          >
            Workshop Board
          </span>
        </div>

        {/* Kanban columns */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 0,
            padding: '16px 14px',
            overflowX: 'auto',
          }}
        >
          {KANBAN_COLUMNS.map((col, ci) => (
            <div
              key={col.label}
              style={{
                padding: '0 6px',
                borderRight: ci < KANBAN_COLUMNS.length - 1 ? '1px solid #EBE2D6' : 'none',
              }}
            >
              {/* Column header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 99,
                    backgroundColor: col.dot,
                    display: 'inline-block',
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: '0.62rem',
                    fontWeight: 700,
                    color: 'var(--cafe-text)',
                    letterSpacing: '0.03em',
                    lineHeight: 1.2,
                  }}
                >
                  {col.label}
                </span>
              </div>
              {/* Cards */}
              {col.cards.map((card) => (
                <div key={card} className="lp-kanban-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: 99,
                        backgroundColor: col.dot,
                        display: 'inline-block',
                        flexShrink: 0,
                        opacity: 0.8,
                      }}
                    />
                    <span style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--cafe-text)', lineHeight: 1.3 }}>
                      {card}
                    </span>
                  </div>
                  <div
                    style={{
                      height: 4,
                      borderRadius: 99,
                      backgroundColor: col.color,
                      border: `1px solid ${col.dot}33`,
                    }}
                  />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ─── Hero ─── */

function HeroSection() {
  return (
    <section className="grid grid-cols-1 gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:gap-14 lg:items-center">
      {/* Left column */}
      <div>
        {/* Eyebrow */}
        <div
          className="lp-reveal inline-flex items-center gap-2 rounded-full px-3.5 py-1.5"
          style={{
            backgroundColor: '#F3ECE2',
            border: '1px solid #E2D7C8',
            color: 'var(--cafe-espresso)',
          }}
        >
          <span
            style={{
              fontSize: '0.65rem',
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              fontWeight: 700,
            }}
          >
            Built by a repair shop owner, for repair shop owners
          </span>
        </div>

        {/* H1 */}
        <h1
          className="lp-reveal lp-reveal-delay-1 mt-5 text-4xl leading-tight sm:text-5xl lg:text-[3.2rem]"
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            color: 'var(--cafe-text)',
            fontWeight: 700,
            letterSpacing: '-0.01em',
          }}
        >
          Run your repair shop like a pro
        </h1>

        {/* Subheading */}
        <p
          className="lp-reveal lp-reveal-delay-2 mt-5 max-w-xl text-base sm:text-lg"
          style={{ color: 'var(--cafe-text-mid)', lineHeight: 1.75 }}
        >
          Mainspring tracks every job from intake to collection across watches, shoes, and mobile key
          services. One workshop, one dashboard, zero jobs slipping through the cracks.
        </p>

        {/* CTAs */}
        <div className="lp-reveal lp-reveal-delay-3 mt-7 flex flex-wrap items-center gap-3">
          <Link
            to="/signup"
            className="lp-btn inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold"
            style={{
              backgroundColor: 'var(--cafe-amber)',
              color: '#fff',
              boxShadow: '0 4px 14px rgba(120,76,20,0.28)',
            }}
          >
            Start free trial
            <ArrowRight size={16} />
          </Link>
          <Link
            to="/login"
            className="lp-btn inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold"
            style={{
              backgroundColor: 'transparent',
              color: 'var(--cafe-text)',
              border: '1.5px solid var(--cafe-border)',
            }}
          >
            Log in
          </Link>
        </div>

        {/* Social proof pills */}
        <div className="lp-reveal lp-reveal-delay-4 mt-6 flex flex-wrap gap-2">
          {['Watch repairs', 'Shoe repairs', 'Mobile locksmith'].map((pill) => (
            <span
              key={pill}
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold"
              style={{
                backgroundColor: '#F0E9DF',
                color: 'var(--cafe-espresso)',
                border: '1px solid #DFD4C5',
              }}
            >
              <CheckCircle2 size={11} style={{ color: 'var(--cafe-gold-dark)' }} />
              {pill}
            </span>
          ))}
        </div>
      </div>

      {/* Right column — Kanban mockup */}
      <KanbanPreview />
    </section>
  )
}

/* ─── How it works ─── */

const HOW_IT_WORKS = [
  {
    step: '01',
    title: 'Take the job',
    desc: 'Intake in seconds — add the customer, item details, and any notes right at the counter.',
  },
  {
    step: '02',
    title: 'Quote & confirm',
    desc: 'Send a quote, get approval, and schedule the work without touching a spreadsheet.',
  },
  {
    step: '03',
    title: 'Complete & collect',
    desc: 'Mark the job done, auto-generate an invoice, and record payment on the spot.',
  },
]

function HowItWorks() {
  return (
    <section className="lp-reveal lp-reveal-delay-2 mt-20 sm:mt-24">
      <div className="text-center mb-10">
        <h2
          className="text-3xl sm:text-4xl"
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            color: 'var(--cafe-text)',
            fontWeight: 700,
          }}
        >
          From drop-off to done in three steps
        </h2>
      </div>

      <div style={{ position: 'relative' }}>
        {/* Connector line — desktop only */}
        <div
          style={{
            position: 'absolute',
            top: 36,
            left: 'calc(16.66% + 24px)',
            right: 'calc(16.66% + 24px)',
            height: 2,
            background: 'linear-gradient(90deg, var(--cafe-gold) 0%, var(--cafe-amber) 50%, var(--cafe-gold) 100%)',
            opacity: 0.35,
            borderRadius: 99,
          }}
          className="hidden lg:block"
        />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {HOW_IT_WORKS.map(({ step, title, desc }) => (
            <div
              key={step}
              className="lp-card rounded-3xl p-7"
              style={{
                backgroundColor: 'var(--cafe-surface)',
                border: '1px solid var(--cafe-border)',
                boxShadow: '0 2px 8px rgba(90,55,16,0.05)',
                textAlign: 'center',
              }}
            >
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: 52,
                  height: 52,
                  borderRadius: 99,
                  backgroundColor: 'var(--cafe-amber)',
                  color: '#fff',
                  fontFamily: "'Playfair Display', Georgia, serif",
                  fontWeight: 700,
                  fontSize: '1.15rem',
                  marginBottom: 16,
                  boxShadow: '0 4px 12px rgba(120,76,20,0.22)',
                }}
              >
                {step}
              </div>
              <h3
                className="text-xl"
                style={{
                  fontFamily: "'Playfair Display', Georgia, serif",
                  color: 'var(--cafe-text)',
                  fontWeight: 700,
                  marginBottom: 8,
                }}
              >
                {title}
              </h3>
              <p style={{ color: 'var(--cafe-text-mid)', fontSize: '0.9rem', lineHeight: 1.7 }}>
                {desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ─── Service lines ─── */

function ServiceLines() {
  return (
    <section className="lp-reveal lp-reveal-delay-3 mt-20 sm:mt-24">
      <div className="text-center mb-10">
        <h2
          className="text-3xl sm:text-4xl"
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            color: 'var(--cafe-text)',
            fontWeight: 700,
          }}
        >
          Built for every kind of repair shop
        </h2>
        <p className="mt-3 max-w-2xl mx-auto text-sm sm:text-base" style={{ color: 'var(--cafe-text-mid)' }}>
          Whether you specialise in one trade or run all three, Mainspring has a workflow that fits.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {/* Watch Repairs — amber/gold */}
        <article
          className="lp-card rounded-3xl p-7"
          style={{
            backgroundColor: '#FDF8EF',
            border: '2px solid #E8C97A',
            boxShadow: '0 2px 10px rgba(196,152,40,0.10)',
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 48,
              height: 48,
              borderRadius: 14,
              backgroundColor: '#F5E4B0',
              color: '#8D6A0A',
              marginBottom: 16,
            }}
          >
            <Wrench size={22} />
          </span>
          <h3
            className="text-xl mb-2"
            style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              color: 'var(--cafe-espresso)',
              fontWeight: 700,
            }}
          >
            Watch Repairs
          </h3>
          <p className="text-sm mb-5" style={{ color: '#7A5E2E', lineHeight: 1.7 }}>
            Track every timepiece from intake to collection. Manage parts, quotes, and customer
            approvals in a dedicated horological workflow.
          </p>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              'Brand, model & movement tracking',
              'Part sourcing and ETA notes',
              'Customer approval before work begins',
            ].map((item) => (
              <li key={item} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.82rem', color: '#6B4F22' }}>
                <CheckCircle2 size={14} style={{ color: '#C49A1A', flexShrink: 0, marginTop: 2 }} />
                {item}
              </li>
            ))}
          </ul>
        </article>

        {/* Shoe Repairs — warm green */}
        <article
          className="lp-card rounded-3xl p-7"
          style={{
            backgroundColor: '#F2F8F3',
            border: '2px solid #8DC49A',
            boxShadow: '0 2px 10px rgba(80,160,100,0.08)',
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 48,
              height: 48,
              borderRadius: 14,
              backgroundColor: '#C8E8CC',
              color: '#2D7A46',
              marginBottom: 16,
            }}
          >
            <Scissors size={22} />
          </span>
          <h3
            className="text-xl mb-2"
            style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              color: '#1C3D26',
              fontWeight: 700,
            }}
          >
            Shoe Repairs
          </h3>
          <p className="text-sm mb-5" style={{ color: '#365C44', lineHeight: 1.7 }}>
            Catalogue-based services and quick quotes built for cobblers. Batch multiple pairs
            under one job and keep the bench moving.
          </p>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              'Pre-built service catalogue with prices',
              'Multi-item jobs under one customer',
              'SMS or call when ready for collection',
            ].map((item) => (
              <li key={item} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.82rem', color: '#2E5038' }}>
                <CheckCircle2 size={14} style={{ color: '#3A9E5F', flexShrink: 0, marginTop: 2 }} />
                {item}
              </li>
            ))}
          </ul>
        </article>

        {/* Mobile Locksmith — espresso/dark */}
        <article
          className="lp-card rounded-3xl p-7"
          style={{
            backgroundColor: '#2A1F19',
            border: '2px solid #4E3A2C',
            boxShadow: '0 2px 10px rgba(0,0,0,0.18)',
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 48,
              height: 48,
              borderRadius: 14,
              backgroundColor: '#3E2C20',
              color: '#D4A45C',
              marginBottom: 16,
            }}
          >
            <KeyRound size={22} />
          </span>
          <h3
            className="text-xl mb-2"
            style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              color: '#F4E4CC',
              fontWeight: 700,
            }}
          >
            Mobile Locksmith
          </h3>
          <p className="text-sm mb-5" style={{ color: '#C8AB88', lineHeight: 1.7 }}>
            Key cutting, transponder programming, and lockout dispatch — built for automotive
            locksmiths who work on-the-road and in-store.
          </p>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              'Vehicle make, model & key type lookup',
              'Day planner & map view for field techs',
              'Fleet billing and bulk key jobs',
            ].map((item) => (
              <li key={item} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.82rem', color: '#C8A87A' }}>
                <CheckCircle2 size={14} style={{ color: '#D4A45C', flexShrink: 0, marginTop: 2 }} />
                {item}
              </li>
            ))}
          </ul>
        </article>
      </div>
    </section>
  )
}

/* ─── Feature highlight ─── */

const FEATURES = [
  {
    icon: ClipboardCheck,
    title: 'Smart job tracking',
    desc: 'Status pipeline with stage-by-stage visibility across every service line.',
  },
  {
    icon: Users,
    title: 'Customer profiles',
    desc: 'Full history across all service lines — watches, shoes, and keys — in one place.',
  },
  {
    icon: Receipt,
    title: 'Quotes & invoicing',
    desc: 'Send quotes, get approvals, and auto-create invoices when a job is completed.',
  },
  {
    icon: ShoppingCart,
    title: 'POS built in',
    desc: 'Walk-in sales, key cutting, and quick checkout without a separate system.',
  },
  {
    icon: MapPin,
    title: 'Mobile dispatch',
    desc: 'Day planner, week scheduler, and map view for techs working in the field.',
  },
  {
    icon: BarChart3,
    title: 'Reports & commission',
    desc: 'Revenue, job volume, and technician commissions — all calculated automatically.',
  },
]

function FeatureHighlight() {
  return (
    <section
      className="lp-reveal lp-reveal-delay-4 mt-20 sm:mt-24 rounded-[28px] px-8 py-12 sm:px-12 sm:py-14"
      style={{
        background: 'linear-gradient(160deg, #2A1F19 0%, #1E1610 100%)',
        border: '1px solid #4A3728',
        boxShadow: '0 4px 16px rgba(0,0,0,0.16), 0 20px 40px rgba(0,0,0,0.20)',
      }}
    >
      <div className="text-center mb-10">
        <h2
          className="text-3xl sm:text-4xl"
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            color: '#F4E4CC',
            fontWeight: 700,
          }}
        >
          Everything your workshop needs
        </h2>
        <p className="mt-3 max-w-xl mx-auto text-sm sm:text-base" style={{ color: '#B89A78', lineHeight: 1.7 }}>
          No bolt-ons, no third-party integrations. It all ships with Mainspring.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, desc }) => (
          <div
            key={title}
            className="lp-card rounded-2xl p-5"
            style={{
              backgroundColor: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 40,
                height: 40,
                borderRadius: 12,
                backgroundColor: 'rgba(212,164,92,0.15)',
                color: '#D4A45C',
                marginBottom: 12,
              }}
            >
              <Icon size={18} />
            </span>
            <h3
              className="text-base font-semibold mb-1.5"
              style={{ color: '#F4E4CC' }}
            >
              {title}
            </h3>
            <p style={{ color: '#A8876A', fontSize: '0.83rem', lineHeight: 1.65 }}>{desc}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

/* ─── Pricing ─── */

function PricingSection() {
  return (
    <section id="pricing" className="lp-reveal lp-reveal-delay-5 mt-20 sm:mt-24">
      <div className="text-center mb-10">
        <h2
          className="text-3xl sm:text-4xl"
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            color: 'var(--cafe-text)',
            fontWeight: 700,
          }}
        >
          Simple, honest pricing
        </h2>
        <p className="mt-3 text-sm sm:text-base" style={{ color: 'var(--cafe-text-mid)' }}>
          Start with one service line. Add more as you grow. No lock-in.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 max-w-3xl mx-auto">
        {/* Basic */}
        <article
          className="lp-card rounded-3xl p-8"
          style={{
            backgroundColor: 'var(--cafe-surface)',
            border: '1.5px solid var(--cafe-border)',
            boxShadow: '0 2px 8px rgba(90,55,16,0.05)',
          }}
        >
          <p
            className="text-xs font-semibold uppercase tracking-widest mb-3"
            style={{ color: 'var(--cafe-text-muted)' }}
          >
            Basic
          </p>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 4 }}>
            <span
              style={{
                fontFamily: "'Playfair Display', Georgia, serif",
                fontSize: '2.4rem',
                fontWeight: 700,
                color: 'var(--cafe-text)',
                lineHeight: 1,
              }}
            >
              A$25
            </span>
            <span style={{ color: 'var(--cafe-text-muted)', fontSize: '0.85rem' }}>/month</span>
          </div>
          <p className="text-sm mb-6" style={{ color: 'var(--cafe-text-mid)' }}>
            One service line
          </p>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              'Choose Watch, Shoe, or Mobile Services',
              'Full job tracking, POS & invoicing',
              'Unlimited customers and jobs',
            ].map((b) => (
              <li key={b} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.85rem', color: 'var(--cafe-text-mid)' }}>
                <CheckCircle2 size={15} style={{ color: 'var(--cafe-gold-dark)', flexShrink: 0, marginTop: 2 }} />
                {b}
              </li>
            ))}
          </ul>
        </article>

        {/* Pro — highlighted */}
        <article
          className="lp-card rounded-3xl p-8"
          style={{
            backgroundColor: '#FDF8EE',
            border: '2px solid var(--cafe-amber)',
            boxShadow: '0 4px 16px rgba(186,120,32,0.15)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <p
              className="text-xs font-semibold uppercase tracking-widest"
              style={{ color: '#8D6420' }}
            >
              Pro
            </p>
            <span
              style={{
                fontSize: '0.65rem',
                fontWeight: 700,
                backgroundColor: 'var(--cafe-amber)',
                color: '#fff',
                borderRadius: 99,
                padding: '3px 10px',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              Best value
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 4 }}>
            <span
              style={{
                fontFamily: "'Playfair Display', Georgia, serif",
                fontSize: '2.4rem',
                fontWeight: 700,
                color: 'var(--cafe-espresso)',
                lineHeight: 1,
              }}
            >
              A$50
            </span>
            <span style={{ color: '#8D6420', fontSize: '0.85rem' }}>/month</span>
          </div>
          <p className="text-sm mb-6" style={{ color: '#7A5E2E' }}>
            Everything, all service lines
          </p>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              'All three service lines unlocked',
              'Reports, commissions & multi-site',
              'Priority support from the founders',
            ].map((b) => (
              <li key={b} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.85rem', color: '#6B4F22' }}>
                <CheckCircle2 size={15} style={{ color: 'var(--cafe-amber)', flexShrink: 0, marginTop: 2 }} />
                {b}
              </li>
            ))}
          </ul>
        </article>
      </div>

      {/* Add-on note */}
      <p
        className="mt-6 text-center text-sm"
        style={{ color: 'var(--cafe-text-muted)' }}
      >
        <Plus size={13} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />
        Add extra service lines for A$10/month each on the Basic plan.
      </p>
    </section>
  )
}

/* ─── Final CTA ─── */

function FinalCTA() {
  return (
    <section className="lp-reveal lp-reveal-delay-6 mt-20 sm:mt-24 mb-12">
      <div
        className="rounded-[28px] px-8 py-14 text-center"
        style={{
          background: 'linear-gradient(160deg, #332821 0%, #1E1610 100%)',
          border: '1px solid #4E3D32',
          boxShadow: '0 4px 16px rgba(0,0,0,0.16), 0 20px 40px rgba(0,0,0,0.20)',
        }}
      >
        <Sparkles size={28} style={{ color: 'var(--cafe-gold)', margin: '0 auto 16px' }} />
        <h2
          className="text-3xl sm:text-4xl"
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            color: '#F4E8D7',
            fontWeight: 700,
            maxWidth: 560,
            margin: '0 auto',
            lineHeight: 1.25,
          }}
        >
          Start running a tighter shop today
        </h2>
        <div className="mt-8">
          <Link
            to="/signup"
            className="lp-btn inline-flex items-center gap-2 rounded-xl px-8 py-3.5 text-sm font-semibold"
            style={{
              backgroundColor: 'var(--cafe-gold)',
              color: 'var(--cafe-espresso)',
              boxShadow: '0 5px 16px rgba(201,162,72,0.30)',
            }}
          >
            Start free trial
            <ArrowRight size={16} />
          </Link>
        </div>
        <p className="mt-4 text-sm" style={{ color: '#A8876A' }}>
          No credit card required. Set up in minutes.
        </p>
      </div>
    </section>
  )
}

/* ─── Root export ─── */

export default function LandingPage() {
  const { token, sessionReady } = useAuth()

  // After /auth/session succeeds, send signed-in users straight to the app.
  if (token && sessionReady) return <Navigate to="/dashboard" replace />

  return (
    <div
      className="min-h-screen"
      style={{
        background: 'linear-gradient(180deg, #FAF6F0 0%, #F2EAE0 54%, #EAE0D4 100%)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <style>{LANDING_CSS}</style>

      {/* Subtle radial glow */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background:
            'radial-gradient(ellipse 980px 520px at 50% 8%, rgba(184,149,86,0.09) 0%, rgba(122,93,46,0.03) 38%, transparent 70%)',
        }}
      />

      <div
        className="mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8"
        style={{ position: 'relative', zIndex: 1 }}
      >
        {/* ── Header ── */}
        <header className="flex items-center justify-between py-6 sm:py-7">
          <div className="flex items-center">
            <img
              src="/mainspring-logo.svg"
              alt="Mainspring"
              className="w-28 sm:w-40"
              style={{ height: 'auto' }}
            />
          </div>
          <nav className="flex items-center gap-2 sm:gap-3">
            <a
              href="#pricing"
              className="hidden sm:inline-flex rounded-lg px-3 py-2 text-sm font-medium"
              style={{ color: 'var(--cafe-text)' }}
            >
              Pricing
            </a>
            <Link
              to="/login"
              className="lp-btn rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap"
              style={{ color: 'var(--cafe-text)' }}
            >
              Log in
            </Link>
            <Link
              to="/signup"
              className="lp-btn rounded-xl px-4 py-2.5 text-sm font-semibold whitespace-nowrap"
              style={{
                backgroundColor: 'var(--cafe-amber)',
                color: '#fff',
                boxShadow: '0 3px 10px rgba(120,76,20,0.22)',
              }}
            >
              Start free trial
            </Link>
          </nav>
        </header>

        {/* ── Page sections ── */}
        <HeroSection />
        <HowItWorks />
        <ServiceLines />
        <FeatureHighlight />
        <PricingSection />
        <FinalCTA />
      </div>

      {/* ── Footer ── */}
      <footer
        style={{
          borderTop: '1px solid var(--cafe-border)',
          backgroundColor: 'var(--cafe-paper)',
          marginTop: 0,
          padding: '24px 0',
        }}
      >
        <div
          className="mx-auto flex max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8"
          style={{ flexWrap: 'wrap', gap: 12 }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <img
              src="/mainspring-logo.svg"
              alt="Mainspring"
              style={{ height: 24, width: 'auto' }}
            />
            <span style={{ fontSize: '0.8rem', color: 'var(--cafe-text-muted)' }}>
              &copy; 2026 Mainspring
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <a
              href="#pricing"
              style={{ fontSize: '0.82rem', color: 'var(--cafe-text-mid)', textDecoration: 'none' }}
            >
              Pricing
            </a>
            <Link
              to="/login"
              style={{ fontSize: '0.82rem', color: 'var(--cafe-text-mid)', textDecoration: 'none' }}
            >
              Log in
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
