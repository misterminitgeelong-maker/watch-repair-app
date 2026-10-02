import { useEffect } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { MKT, MARKETING_CSS } from '@/lib/marketingTheme'

/**
 * Landing page for mobile operators (mobile locksmiths, auto key / car key).
 * Same editorial look as the main landing page; every claim below maps to a
 * screen that exists in the app (quote and invoice links, directions, arrival
 * SMS, key photo intake, known-issue warnings, lead inbox).
 */

const STEPS = [
  { n: '01', label: 'Job in', body: 'Take the call, add the customer and vehicle, pick the job type. Send the customer a link to add their address and a photo of the key.' },
  { n: '02', label: 'On the way', body: 'Get directions from the job and text the customer that you are arriving, in two taps.' },
  { n: '03', label: 'Quote', body: 'Quote from your own price list and text the customer a link. They approve on their phone.' },
  { n: '04', label: 'Invoice', body: 'Invoice from the job before you leave. The customer gets a link to view it and pay by card.' },
]

const FEATURES = [
  { title: 'Your price list', body: 'Retail and trade prices, callout included or added, set once and reused on every quote.' },
  { title: 'Vehicle warnings before you start', body: 'Known issues and recommended tools for the car show on the job, so a locked gateway or a cloned chip is not a surprise in the driveway.' },
  { title: 'Photos from the phone', body: 'Customers send a photo of the key. You attach photos to the job from the camera.' },
  { title: 'Leads and dispatch', body: 'Enquiries land in a lead inbox. See your jobs on a map and a week view, and assign them to your team.' },
  { title: 'Built for one hand', body: 'Big buttons, tap-to-call and tap-to-navigate on every job, and a job list that shows who and what at a glance.' },
  { title: 'Texts from the job', body: 'Quote, arrival and pickup messages go from the job, not from your personal number.' },
]

const rule = (c: string = MKT.ink) => `1px solid ${c}`

export default function MobileServicesLandingPage() {
  const { token, sessionReady } = useAuth()

  useEffect(() => {
    const prev = document.title
    document.title = 'Mobile locksmith and auto key software | Mainspring'
    return () => { document.title = prev }
  }, [])

  useEffect(() => {
    const saved = document.documentElement.getAttribute('data-theme')
    document.documentElement.removeAttribute('data-theme')
    return () => {
      if (saved) document.documentElement.setAttribute('data-theme', saved)
    }
  }, [])

  if (token && sessionReady) return <Navigate to="/dashboard" replace />

  return (
    <div className="mkt-landing min-h-screen">
      <style>{MARKETING_CSS}</style>

      <div style={{ borderBottom: `2px solid ${MKT.ink}`, background: MKT.paper }}>
        <div className="mx-auto flex w-full items-center justify-between" style={{ maxWidth: 1320, padding: '18px 20px' }}>
          <Link to="/" className="flex items-center gap-3" aria-label="Mainspring home">
            <img src="/marketing/mainspring-badge-vermilion.svg" alt="" style={{ width: 34, height: 34 }} />
            <span className="mkt-serif hidden min-[420px]:inline" style={{ fontSize: 21, fontWeight: 700, color: MKT.ink }}>Mainspring</span>
          </Link>
          <nav className="flex items-center gap-4">
            <Link to="/login" className="inline-flex items-center" style={{ fontSize: 13, fontWeight: 600, color: MKT.ink, minHeight: 44 }}>Log in</Link>
            <Link to="/signup" className="mkt-nav-cta inline-flex items-center whitespace-nowrap px-3 sm:px-4" style={{ height: 42, fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Start free trial
            </Link>
          </nav>
        </div>
      </div>

      <div style={{ background: MKT.oatmeal }}>
        <div className="mx-auto w-full" style={{ maxWidth: 1320, padding: '48px 20px 56px' }}>
          <p style={{ margin: 0, fontSize: 11, fontWeight: 700, letterSpacing: '0.3em', textTransform: 'uppercase', color: MKT.vermilionDeep }}>
            Mobile locksmiths · Auto key · Car key
          </p>
          <h1 style={{ margin: '18px 0 0', fontSize: 'clamp(40px, 8vw, 104px)', lineHeight: 0.9, fontWeight: 800, letterSpacing: '-0.06em', color: MKT.ink }}>
            Quote, invoice and<br />get paid before<br />you leave the driveway.
          </h1>
          <p style={{ margin: '28px 0 0', maxWidth: 560, fontSize: 17, lineHeight: 1.6, color: MKT.textBody }}>
            Mainspring replaces the paper job book. Take the job, text a quote, invoice on site, and see what you are owed, all from your phone.
          </p>
          <div className="flex flex-wrap gap-3" style={{ marginTop: 28 }}>
            <Link to="/signup" className="mkt-btn-primary inline-flex items-center whitespace-nowrap" style={{ height: 54, padding: '0 26px', fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
              Start free trial
            </Link>
            <Link to="/login?demo=1" className="mkt-btn-outline-ink inline-flex items-center whitespace-nowrap" style={{ height: 54, padding: '0 26px', fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
              Try the demo
            </Link>
          </div>
          <p style={{ margin: '14px 0 0', fontSize: 13, color: MKT.textBody }}>14-day trial · from A$50 a month · Australian-owned, built in Geelong</p>
        </div>
      </div>

      <div style={{ borderBottom: rule() }}>
        <div className="mx-auto grid w-full grid-cols-1 sm:grid-cols-2 lg:grid-cols-4" style={{ maxWidth: 1320 }}>
          {STEPS.map(s => (
            <div key={s.n} style={{ padding: '30px 22px 34px', borderLeft: rule(MKT.ruleMid), borderTop: rule(MKT.ruleMid) }}>
              <p style={{ margin: 0, fontSize: 'clamp(36px, 5vw, 56px)', fontWeight: 800, letterSpacing: '-0.055em', color: MKT.vermilion, lineHeight: 0.88 }}>{s.n}</p>
              <p style={{ margin: '14px 0 0', fontSize: 12, fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: MKT.ink }}>{s.label}</p>
              <p style={{ margin: '10px 0 0', fontSize: 14, lineHeight: 1.6, color: MKT.textBody }}>{s.body}</p>
            </div>
          ))}
        </div>
      </div>

      <div style={{ borderBottom: rule() }}>
        <div className="mx-auto w-full" style={{ maxWidth: 1320, padding: '48px 20px 52px' }}>
          <h2 style={{ margin: 0, maxWidth: 640, fontSize: 'clamp(30px, 4.4vw, 46px)', lineHeight: 1.0, fontWeight: 800, letterSpacing: '-0.05em', color: MKT.ink }}>
            Made for the van, not the shop counter.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3" style={{ marginTop: 28, border: rule() }}>
            {FEATURES.map(f => (
              <div key={f.title} style={{ padding: '24px 22px 28px', borderLeft: rule(MKT.ruleMid), borderTop: rule(MKT.ruleMid), background: MKT.paper }}>
                <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, letterSpacing: '-0.03em', color: MKT.ink }}>{f.title}</h3>
                <p style={{ margin: '10px 0 0', fontSize: 14, lineHeight: 1.6, color: MKT.textBody }}>{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ background: MKT.vermilion }}>
        <div className="mx-auto flex w-full flex-wrap items-end justify-between gap-8" style={{ maxWidth: 1320, padding: '54px 20px 58px' }}>
          <div style={{ maxWidth: 680 }}>
            <h2 style={{ margin: 0, fontSize: 'clamp(34px, 6vw, 58px)', lineHeight: 0.96, fontWeight: 800, letterSpacing: '-0.06em', color: MKT.white }}>
              Put the job book down.
            </h2>
            <p style={{ margin: '16px 0 0', maxWidth: 460, fontSize: 15, lineHeight: 1.65, color: MKT.ink }}>
              Set up in ten minutes. Not sure yet? Open the demo shop and tap through a real key job.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to="/signup" className="mkt-btn-close-primary inline-flex items-center whitespace-nowrap px-4 sm:px-[26px]" style={{ height: 56, fontSize: 12, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
              Start free trial
            </Link>
            <a href="mailto:admin@mainspring.au" className="mkt-btn-close-outline inline-flex items-center whitespace-nowrap px-4 sm:px-[26px]" style={{ height: 56, fontSize: 12, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
              Talk to us
            </a>
          </div>
        </div>
      </div>

      <div style={{ background: MKT.oatmealDeep }}>
        <div className="mx-auto flex w-full flex-wrap items-center justify-between gap-5" style={{ maxWidth: 1320, padding: '22px 20px' }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.textBody }}>© 2026 · mainspring.au</span>
          <div className="flex flex-wrap gap-5">
            <Link to="/" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.textBody }}>All trades</Link>
            <Link to="/privacy" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.textBody }}>Privacy</Link>
            <a href="mailto:admin@mainspring.au" style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase', color: MKT.textBody }}>Contact</a>
          </div>
        </div>
      </div>
    </div>
  )
}
