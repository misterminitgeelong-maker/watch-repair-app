import { useEffect } from 'react'
import { Link } from 'react-router-dom'

const LANDING_CSS = `
.lp-reveal { opacity: 0; animation: lpFadeUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) forwards; }
@keyframes lpFadeUp { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
.lp-card { transition: transform 0.2s ease, box-shadow 0.2s ease; }
.lp-card:hover { transform: translateY(-3px); box-shadow: 0 6px 14px rgba(90, 55, 16, 0.08), 0 18px 34px rgba(90, 55, 16, 0.10); }
`

const SEO_TITLE = 'Mainspring Pricing — Repair OS for watchmakers, shoe repairs, and mobile services. From A$25/month.'
const SEO_DESCRIPTION = 'Mainspring Pricing — Repair OS for watchmakers, shoe repairs, and mobile services. From A$25/month.'

export default function PricingPage() {
  useEffect(() => {
    document.title = SEO_TITLE
    let meta = document.querySelector('meta[name="description"]')
    if (!meta) {
      meta = document.createElement('meta')
      meta.setAttribute('name', 'description')
      document.head.appendChild(meta)
    }
    meta.setAttribute('content', SEO_DESCRIPTION)
    return () => {
      document.title = 'Mainspring'
      meta?.setAttribute('content', '')
    }
  }, [])

  const plans = [
    {
      title: 'Basic',
      price: 'A$25/mo',
      note: 'Includes one service tab + reports',
      bullets: [
        'Choose one tab: Watch Repairs, Shoe Repairs, or Mobile Services',
        'Add each extra service tab for $10/month',
        'Customers and invoicing included',
      ],
    },
    {
      title: 'Pro',
      price: 'A$50/mo',
      note: 'Full app access',
      bullets: [
        'All service tabs unlocked',
        'Reports, customer accounts, and multi-site features',
        'Best for growing workshops and teams',
      ],
    },
  ]

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
      <div
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background: 'radial-gradient(ellipse 980px 520px at 50% 8%, rgba(184,149,86,0.08) 0%, rgba(122,93,46,0.03) 38%, transparent 70%)',
        }}
      />
      <div className="mx-auto w-full max-w-6xl" style={{ position: 'relative', zIndex: 1 }}>
        <header className="flex items-center justify-between py-6 sm:py-7">
          <Link to="/" className="flex items-center gap-3">
            <img src="/mainspring-logo.svg" alt="Mainspring" className="w-28 sm:w-44" style={{ height: 'auto' }} />
          </Link>
          <div className="flex items-center gap-2 sm:gap-3">
            <Link to="/pricing" className="hidden sm:inline-flex rounded-lg px-3 py-2 text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>
              Pricing
            </Link>
            <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap" style={{ color: 'var(--cafe-text)' }}>
              Log in
            </Link>
            <Link
              to="/login?demo=1"
              className="hidden sm:inline-flex rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap"
              style={{ color: '#6A513B', backgroundColor: '#F1E7D8', border: '1px solid #DFD2C2' }}
            >
              Demo login
            </Link>
            <Link
              to="/signup"
              className="rounded-lg px-3.5 py-2 text-sm font-semibold whitespace-nowrap"
              style={{ backgroundColor: '#F3ECE2', color: '#5F4734', border: '1px solid #DFD2C2' }}
            >
              <span className="sm:hidden">Get started</span>
              <span className="hidden sm:inline">Start your shop</span>
            </Link>
          </div>
        </header>

        <section id="pricing" className="lp-reveal mt-16 sm:mt-20">
          <div className="text-center">
            <h1 className="text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
              Clear pricing with no surprises
            </h1>
            <p className="mt-3 text-sm sm:text-base" style={{ color: 'var(--cafe-text-mid)' }}>
              Start with Basic at A$25/month, add service tabs at A$10/month each, or move to Pro at A$50/month for full access.
            </p>
          </div>

          <div className="mt-7 grid grid-cols-1 gap-4 md:grid-cols-2">
            {plans.map((plan) => (
              <article
                key={plan.title}
                className="lp-card rounded-3xl p-6"
                style={{
                  backgroundColor: 'var(--cafe-surface)',
                  border: '1px solid var(--cafe-border)',
                  boxShadow: '0 2px 8px rgba(90,55,16,0.05)',
                }}
              >
                <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: '#8D6420' }}>
                  {plan.title}
                </p>
                <p className="mt-2 text-3xl" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
                  {plan.price}
                </p>
                <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
                  {plan.note}
                </p>
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
            <p className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>
              Full monthly breakdown (AUD)
            </p>
            <div className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2" style={{ color: 'var(--cafe-text-mid)' }}>
              <p>Basic 1 tab: A$25/month</p>
              <p>Basic 2 tabs: A$35/month</p>
              <p>Basic 3 tabs: A$45/month</p>
              <p>Pro all features: A$50/month</p>
            </div>
          </div>

          <div className="mt-8 flex justify-center">
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold"
              style={{ backgroundColor: 'var(--cafe-gold)', color: 'var(--cafe-espresso)', boxShadow: '0 5px 16px rgba(201,162,72,0.25)' }}
            >
              Start your shop
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}
