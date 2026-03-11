import { Navigate, Link } from 'react-router-dom'
import { CheckCircle2, Wrench, Layers3, TimerReset, ClipboardCheck, PackageOpen, Sparkles, ArrowRight } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'

const LANDING_CSS = `
@keyframes lpFadeUp {
  from { opacity: 0; transform: translateY(18px); }
  to { opacity: 1; transform: translateY(0); }
}
.lp-reveal {
  opacity: 0;
  animation: lpFadeUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
.lp-reveal-delay-1 { animation-delay: 0.08s; }
.lp-reveal-delay-2 { animation-delay: 0.16s; }
.lp-reveal-delay-3 { animation-delay: 0.24s; }
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
            Built by watchmakers
          </span>
        </div>

        <h1
          className="mt-5 text-4xl leading-tight sm:text-5xl"
          style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)', fontWeight: 600 }}
        >
          Repair OS for modern watchmakers.
        </h1>
        <p className="mt-5 max-w-xl text-base sm:text-lg" style={{ color: 'var(--cafe-text-mid)', lineHeight: 1.7 }}>
          Mainspring helps your workshop track every repair, move jobs through the bench with clarity, and keep operations visible from intake to collection.
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
        </div>

        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            { title: 'Track every job', icon: Wrench },
            { title: 'Stay organised', icon: Layers3 },
            { title: 'Run the workshop', icon: TimerReset },
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
            Overview
          </h3>
          <span className="rounded-full px-2.5 py-1 text-xs font-semibold" style={{ backgroundColor: '#EFE9DF', color: '#6E5640' }}>
            Live workflow
          </span>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          {[
            ['Open Jobs', '34'],
            ['Awaiting Go-Ahead', '9'],
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
            <h4 className="text-sm font-semibold uppercase tracking-wide">Repair Pipeline</h4>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {['Received', 'Diagnosing', 'Awaiting Go Ahead', 'Awaiting Parts', 'Repairing', 'Quality Check', 'Ready', 'Collected'].map((stage) => (
              <span
                key={stage}
                className="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                style={{ backgroundColor: '#EFE9DF', color: '#62503E', border: '1px solid #E2D7C8' }}
              >
                <span style={{ fontSize: '0.52rem', marginRight: 6, opacity: 0.8 }}>●</span>
                {stage}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function ValueProps() {
  const cards = [
    {
      title: 'Intake to collection',
      text: 'Every repair stays visible from customer drop-off through final collection, with no status gaps.',
      icon: CheckCircle2,
    },
    {
      title: 'Built around repair flow',
      text: 'Stages, quotes, parts, and workshop decisions follow how watchmakers actually work at the bench.',
      icon: PackageOpen,
    },
    {
      title: 'Keep customers moving',
      text: 'Approve faster, communicate clearly, and avoid bottlenecks with a practical operations view.',
      icon: Sparkles,
    },
  ]

  return (
    <section className="lp-reveal lp-reveal-delay-1 mt-16 sm:mt-20">
      <div className="text-center">
        <h2 className="text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
          Purpose-built for the modern workshop
        </h2>
      </div>
      <div className="mt-7 grid grid-cols-1 gap-4 md:grid-cols-3">
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
    'Receive the watch',
    'Quote and approve',
    'Repair with clarity',
    'Collect and close',
  ]

  return (
    <section className="lp-reveal lp-reveal-delay-2 mt-16 sm:mt-20">
      <div className="text-center">
        <h2 className="text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
          A workflow that matches the bench.
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

function FinalCTA() {
  return (
    <section className="lp-reveal lp-reveal-delay-3 mt-16 sm:mt-20 mb-12">
      <div
        className="rounded-[28px] px-6 py-10 sm:px-10"
        style={{
          background: 'linear-gradient(160deg, #332821 0%, #271F19 100%)',
          border: '1px solid #4E3D32',
          boxShadow: '0 4px 16px rgba(0,0,0,0.16), 0 20px 40px rgba(0,0,0,0.20)',
        }}
      >
        <h2 className="text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: '#F4E8D7' }}>
          Built by watchmakers, for watchmakers.
        </h2>
        <p className="mt-3 max-w-2xl text-sm sm:text-base" style={{ color: '#D8C2A8', lineHeight: 1.75 }}>
          Give your workshop a proper repair pipeline and operations view so every watch, customer, and decision stays on track.
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
        </div>
      </div>
    </section>
  )
}

export default function LandingPage() {
  const { token } = useAuth()

  if (token) return <Navigate to="/dashboard" replace />

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
            <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>Log in</Link>
            <Link to="/signup" className="rounded-lg px-3.5 py-2 text-sm font-semibold" style={{ backgroundColor: '#F3ECE2', color: '#5F4734', border: '1px solid #DFD2C2' }}>
              Start your shop
            </Link>
          </div>
        </header>

        <HeroSection />
        <ValueProps />
        <WorkflowSteps />
        <FinalCTA />
      </div>
    </div>
  )
}
