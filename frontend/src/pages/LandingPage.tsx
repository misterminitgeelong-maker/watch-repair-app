import { Navigate, Link } from 'react-router-dom'
import {
  CheckCircle2,
  Wrench,
  Scissors,
  KeyRound,
  Layers3,
  ClipboardCheck,
  PackageOpen,
  Sparkles,
  ArrowRight,
  BarChart3,
  Receipt,
  Users,
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
`

const SERVICES = [
  {
    title: 'Watch Repairs',
    icon: Wrench,
    desc: 'Track every watch from intake to collection. Quotes, parts, status—all in one place.',
  },
  {
    title: 'Shoe Repairs',
    icon: Scissors,
    desc: 'Catalogue-based services, quick quotes, and clean workflows for cobblers.',
  },
  {
    title: 'Mobile Services',
    icon: KeyRound,
    desc: 'Key cutting, programming, lockouts. Built for automotive locksmiths and key specialists.',
  },
]

function HeroSection() {
  return (
    <section className="grid grid-cols-1 gap-8 lg:grid-cols-[1.06fr_0.94fr] lg:gap-10">
      <div className="lp-reveal">
        <div
          className="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5"
          style={{ backgroundColor: '#F3ECE2', border: '1px solid #E2D7C8', color: 'var(--cafe-espresso)' }}
        >
          <span style={{ fontSize: '0.65rem', letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 600 }}>
            Mainspring
          </span>
          <span style={{ width: 4, height: 4, borderRadius: 99, backgroundColor: 'var(--cafe-gold-dark)' }} />
          <span style={{ fontSize: '0.65rem', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--cafe-text-mid)' }}>
            One platform for all your repair work
          </span>
        </div>

        <h1
          className="mt-5 text-4xl leading-tight sm:text-5xl"
          style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)', fontWeight: 600 }}
        >
          All your repairs. One workspace.
        </h1>
        <p className="mt-5 max-w-xl text-base sm:text-lg" style={{ color: 'var(--cafe-text-mid)', lineHeight: 1.7 }}>
          Mainspring brings watch repairs, shoe repairs, and mobile key services into one workspace. Track every job, run your POS, manage customers, and keep operations visible—from intake to collection.
        </p>

        <div className="mt-7 flex flex-wrap items-center gap-3">
          <Link
            to="/signup"
            className="lp-btn inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold"
            style={{ backgroundColor: 'var(--cafe-amber)', color: '#fff', boxShadow: '0 4px 12px rgba(120,76,20,0.24)' }}
          >
            Start your shop
            <ArrowRight size={16} />
          </Link>
          <Link
            to="/login"
            className="lp-btn inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold"
            style={{
              backgroundColor: 'var(--cafe-surface)',
              color: 'var(--cafe-text)',
              border: '1px solid var(--cafe-border)',
              boxShadow: '0 1px 2px rgba(80,50,15,0.06), 0 6px 16px rgba(80,50,15,0.08)',
            }}
          >
            Log in
          </Link>
          <Link
            to="/login?demo=1"
            className="lp-btn inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold"
            style={{
              backgroundColor: '#EFE5D7',
              color: '#5A4632',
              border: '1px solid #D7C7B2',
            }}
          >
            Try demo
          </Link>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            { title: 'Watches · Shoes · Keys', icon: Layers3 },
            { title: 'POS & Invoicing', icon: Receipt },
            { title: 'Workshop dashboard', icon: BarChart3 },
          ].map(({ title, icon: Icon }) => (
            <div
              key={title}
              className="lp-card rounded-2xl p-4"
              style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)', boxShadow: '0 2px 10px rgba(80,50,15,0.06)' }}
            >
              <div className="flex items-center gap-2.5" style={{ color: 'var(--cafe-text)' }}>
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg" style={{ backgroundColor: '#EEE6DA', color: '#8D6420' }}>
                  <Icon size={16} />
                </span>
                <span className="text-sm font-semibold">{title}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <ProductPreview />
    </section>
  )
}

function ProductPreview() {
  return (
    <div className="lp-reveal lp-reveal-delay-1">
      <div
        className="lp-card rounded-3xl p-5 sm:p-6"
        style={{
          backgroundColor: 'var(--cafe-surface)',
          border: '1px solid #E8DDCE',
          boxShadow: '0 2px 8px rgba(90,55,16,0.06), 0 18px 42px rgba(90,55,16,0.11)',
        }}
      >
        <div className="flex items-center justify-between">
          <h3 style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }} className="text-xl font-semibold">
            Workshop overview
          </h3>
          <span className="rounded-full px-2.5 py-1 text-xs font-semibold" style={{ backgroundColor: '#EFE9DF', color: '#6E5640' }}>
            Live
          </span>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          {[
            ['Open Jobs', '34'],
            ['Awaiting Approval', '9'],
            ['Awaiting Parts', '6'],
            ['Outstanding', '$12,840'],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl p-3.5" style={{ backgroundColor: '#FBF8F3', border: '1px solid #E7DDD0' }}>
              <p className="text-xs uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>{label}</p>
              <p className="mt-1 text-xl font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>{value}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 rounded-2xl p-4" style={{ backgroundColor: '#F7F1E8', border: '1px solid #E5DACB' }}>
          <div className="flex items-center gap-2" style={{ color: 'var(--cafe-text)' }}>
            <ClipboardCheck size={16} style={{ color: '#8D6420' }} />
            <h4 className="text-sm font-semibold uppercase tracking-wide">Service tabs</h4>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {['Watch Repairs', 'Shoe Repairs', 'Mobile Services'].map((tab) => (
              <span
                key={tab}
                className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                style={{ backgroundColor: '#EFE9DF', color: '#62503E', border: '1px solid #E2D7C8' }}
              >
                <span style={{ fontSize: '0.52rem', marginRight: 6, opacity: 0.8 }}>●</span>
                {tab}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function ServicesSection() {
  return (
    <section className="lp-reveal lp-reveal-delay-1 mt-16 sm:mt-20">
      <div className="text-center">
        <h2 className="text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
          One platform, three service lines
        </h2>
        <p className="mt-3 max-w-2xl mx-auto text-sm sm:text-base" style={{ color: 'var(--cafe-text-mid)' }}>
          Whether you do watches, shoes, keys, or a mix—Mainspring keeps everything organised and visible.
        </p>
      </div>
      <div className="mt-7 grid grid-cols-1 gap-4 md:grid-cols-3">
        {SERVICES.map(({ title, icon: Icon, desc }) => (
          <article
            key={title}
            className="lp-card rounded-3xl p-6"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)', boxShadow: '0 2px 8px rgba(90,55,16,0.05)' }}
          >
            <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl" style={{ backgroundColor: '#EEE6DA', color: '#8D6420' }}>
              <Icon size={24} />
            </span>
            <h3 className="mt-4 text-xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
              {title}
            </h3>
            <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-mid)', lineHeight: 1.7 }}>{desc}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

function ValueProps() {
  const cards = [
    {
      title: 'Intake to collection',
      text: 'Every repair—watch, shoe, or key—stays visible from drop-off through final collection.',
      icon: CheckCircle2,
    },
    {
      title: 'Built around repair flow',
      text: 'Stages, quotes, parts, and workshop decisions follow how repair shops actually work.',
      icon: PackageOpen,
    },
    {
      title: 'POS & invoicing',
      text: 'Take payments, send invoices, track cash, EFTPOS, and bank transfers in one place.',
      icon: Receipt,
    },
    {
      title: 'Customers at the centre',
      text: 'One customer profile links watches, shoes, keys, and service history across all lines.',
      icon: Users,
    },
    {
      title: 'Workshop visibility',
      text: 'See bottlenecks, stage dashboards, and KPIs so you can run the bench with clarity.',
      icon: BarChart3,
    },
    {
      title: 'Scale your shop',
      text: 'Add service tabs as you grow. Multi-site support for franchisees and groups.',
      icon: Sparkles,
    },
  ]

  return (
    <section className="lp-reveal lp-reveal-delay-2 mt-16 sm:mt-20">
      <div className="text-center">
        <h2 className="text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
          Everything your repair shop needs
        </h2>
      </div>
      <div className="mt-7 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map(({ title, text, icon: Icon }) => (
          <article
            key={title}
            className="lp-card rounded-3xl p-6"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)', boxShadow: '0 2px 8px rgba(90,55,16,0.05)' }}
          >
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl" style={{ backgroundColor: '#EEE6DA', color: '#8D6420' }}>
              <Icon size={18} />
            </span>
            <h3 className="mt-4 text-xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
              {title}
            </h3>
            <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-mid)', lineHeight: 1.7 }}>{text}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

function WorkflowSteps() {
  const steps = [
    'Receive & quote',
    'Approve & schedule',
    'Complete the work',
    'Invoice & collect',
  ]

  return (
    <section className="lp-reveal lp-reveal-delay-2 mt-16 sm:mt-20">
      <div className="text-center">
        <h2 className="text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
          A workflow that matches the shop
        </h2>
      </div>
      <div className="mt-7 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map((step, i) => (
          <article
            key={step}
            className="lp-card rounded-3xl p-5"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)', boxShadow: '0 2px 8px rgba(90,55,16,0.05)' }}
          >
            <span className="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold" style={{ backgroundColor: '#EEE6DA', color: '#8D6420' }}>
              Step {i + 1}
            </span>
            <h3 className="mt-3 text-lg" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
              {step}
            </h3>
          </article>
        ))}
      </div>
    </section>
  )
}

function PricingSection() {
  const plans = [
    {
      title: 'Basic',
      price: 'A$25/mo',
      note: 'One service tab + reports',
      bullets: [
        'Choose one tab: Watch, Shoe, or Mobile Services',
        'Add each extra tab for $10/month',
        'Customers and invoicing included',
      ],
    },
    {
      title: 'Pro',
      price: 'A$50/mo',
      note: 'Full access',
      bullets: [
        'All service tabs unlocked',
        'Reports, customer accounts, multi-site',
        'Best for growing shops and teams',
      ],
    },
  ]

  return (
    <section id="pricing" className="lp-reveal lp-reveal-delay-3 mt-16 sm:mt-20">
      <div className="text-center">
        <h2 className="text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
          Clear pricing
        </h2>
        <p className="mt-3 text-sm sm:text-base" style={{ color: 'var(--cafe-text-mid)' }}>
          Basic from A$25/month, add tabs at A$10 each, or Pro at A$50 for everything.
        </p>
      </div>

      <div className="mt-7 grid grid-cols-1 gap-4 md:grid-cols-2">
        {plans.map((plan) => (
          <article
            key={plan.title}
            className="lp-card rounded-3xl p-6"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)', boxShadow: '0 2px 8px rgba(90,55,16,0.05)' }}
          >
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: '#8D6420' }}>{plan.title}</p>
            <p className="mt-2 text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>{plan.price}</p>
            <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>{plan.note}</p>
            <ul className="mt-4 space-y-2">
              {plan.bullets.map((bullet) => (
                <li key={bullet} className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
                  • {bullet}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>

      <div className="mt-6 rounded-3xl p-5" style={{ backgroundColor: '#FBF8F3', border: '1px solid #E7DDD0' }}>
        <p className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>Full breakdown (AUD)</p>
        <div className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2" style={{ color: 'var(--cafe-text-mid)' }}>
          <p>Basic 1 tab: A$25/month</p>
          <p>Basic 2 tabs: A$35/month</p>
          <p>Basic 3 tabs: A$45/month</p>
          <p>Pro all features: A$50/month</p>
        </div>
      </div>
    </section>
  )
}

function FinalCTA() {
  return (
    <section className="lp-reveal lp-reveal-delay-4 mt-16 sm:mt-20 mb-12">
      <div
        className="rounded-[28px] px-6 py-10 sm:px-10"
        style={{
          background: 'linear-gradient(160deg, #332821 0%, #271F19 100%)',
          border: '1px solid #4E3D32',
          boxShadow: '0 4px 16px rgba(0,0,0,0.16), 0 20px 40px rgba(0,0,0,0.20)',
        }}
      >
        <h2 className="text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: '#F4E8D7' }}>
          Built for repair shops, by people who run them.
        </h2>
        <p className="mt-3 max-w-2xl text-sm sm:text-base" style={{ color: '#D8C2A8', lineHeight: 1.75 }}>
          Watches, shoes, keys—one platform that keeps every job visible and every customer on track. Designed by a working Mister Minit franchisee.
        </p>

        <div className="mt-7 flex flex-wrap items-center gap-3">
          <Link
            to="/signup"
            className="lp-btn inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold"
            style={{ backgroundColor: 'var(--cafe-gold)', color: 'var(--cafe-espresso)', boxShadow: '0 5px 16px rgba(201,162,72,0.25)' }}
          >
            Start your shop
          </Link>
          <Link
            to="/login"
            className="lp-btn inline-flex items-center rounded-xl px-5 py-3 text-sm font-semibold"
            style={{ border: '1px solid #7A5A3C', color: '#F0DDC4', backgroundColor: 'rgba(255,255,255,0.03)' }}
          >
            Log in
          </Link>
          <Link
            to="/login?demo=1"
            className="lp-btn inline-flex items-center rounded-xl px-5 py-3 text-sm font-semibold"
            style={{ border: '1px solid #8E6A44', color: '#F2DEBC', backgroundColor: 'rgba(255,255,255,0.08)' }}
          >
            Try demo
          </Link>
        </div>
      </div>
    </section>
  )
}

export default function LandingPage() {
  const { token, initializing } = useAuth()

  if (token && !initializing) return <Navigate to="/dashboard" replace />
  if (token && initializing) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)' }}>
        <p className="text-sm">Checking session…</p>
      </div>
    )
  }

  return (
    <div
      className="min-h-screen px-4 sm:px-6 lg:px-8"
      style={{
        background: 'linear-gradient(180deg, #F9F5EF 0%, #F1E9DE 54%, #E8DDD0 100%)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <style>{LANDING_CSS}</style>

      <div style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        background: 'radial-gradient(ellipse 980px 520px at 50% 8%, rgba(184,149,86,0.08) 0%, rgba(122,93,46,0.03) 38%, transparent 70%)',
      }} />

      <div className="mx-auto w-full max-w-6xl" style={{ position: 'relative', zIndex: 1 }}>
        <header className="flex items-center justify-between py-6 sm:py-7">
          <div className="flex items-center gap-3">
            <img src="/mainspring-logo.png" alt="Mainspring" style={{ width: 170, height: 'auto' }} />
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <Link to="/pricing" className="rounded-lg px-3 py-2 text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Pricing</Link>
            <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Log in</Link>
            <Link to="/login?demo=1" className="rounded-lg px-3 py-2 text-sm font-medium" style={{ color: '#6A513B', backgroundColor: '#F1E7D8', border: '1px solid #DFD2C2' }}>
              Demo
            </Link>
            <Link to="/signup" className="rounded-lg px-3.5 py-2 text-sm font-semibold" style={{ backgroundColor: '#F3ECE2', color: '#5F4734', border: '1px solid #DFD2C2' }}>
              Start your shop
            </Link>
          </div>
        </header>

        <HeroSection />
        <ServicesSection />
        <ValueProps />
        <WorkflowSteps />
        <PricingSection />
        <FinalCTA />
      </div>
    </div>
  )
}
