import { useEffect, useRef, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  KeyRound,
  Menu,
  Scissors,
  Watch,
  X,
  ZoomIn,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import './LandingPage.css'

const screens = [
  {
    id: 'watch',
    label: 'Watch repairs',
    image: 'watch-jobs.jpg',
    phoneImage: 'watch-jobs-phone.jpg',
    alt: 'Actual Mainspring watch repair list with customer, status, priority and quote columns',
    description:
      'Know what’s on the bench, waiting for approval or ready to collect.',
  },
  {
    id: 'mobile',
    label: 'Mobile services',
    image: 'mobile-jobs.jpg',
    phoneImage: 'mobile-jobs-phone.jpg',
    alt: 'Actual Mainspring mobile job list with vehicles, technicians and scheduled bookings',
    description:
      'Keep vehicle details, bookings and technicians together for every callout.',
  },
  {
    id: 'invoices',
    label: 'Invoices',
    image: 'invoices.jpg',
    phoneImage: 'invoices-phone.jpg',
    alt: 'Actual Mainspring invoice list showing paid and unpaid demo invoices',
    description:
      'See what’s paid, what’s outstanding and which job it belongs to.',
  },
]

function Brand() {
  return (
    <Link to="/" className="msl-brand" aria-label="Mainspring home">
      <img src="/mainspring-icon.svg" width="36" height="36" alt="" />
      <span>
        Mainspring<span className="msl-brand-dot">.</span>
      </span>
    </Link>
  )
}

function ProductImage({ name, alt }: { name: string; alt: string }) {
  return (
    <img
      src={`/marketing/product/${name}`}
      alt={alt}
      width="1349"
      height="809"
      loading="lazy"
      decoding="async"
    />
  )
}

export default function LandingPage() {
  const { token, sessionReady } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const [screenIndex, setScreenIndex] = useState(0)
  const [expanded, setExpanded] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([])
  const screen = screens[screenIndex]

  useEffect(() => {
    const previousTheme = document.documentElement.getAttribute('data-theme')
    document.documentElement.removeAttribute('data-theme')
    return () => {
      if (previousTheme)
        document.documentElement.setAttribute('data-theme', previousTheme)
      else document.documentElement.removeAttribute('data-theme')
    }
  }, [])

  useEffect(() => {
    if (!expanded) return
    const dialog = dialogRef.current
    const previousOverflow = document.body.style.overflow
    dialog?.showModal()
    document.body.style.overflow = 'hidden'
    return () => {
      dialog?.close()
      document.body.style.overflow = previousOverflow
    }
  }, [expanded])

  if (token && sessionReady) return <Navigate to="/dashboard" replace />

  return (
    <div className="msl-page">
      <a className="msl-skip" href="#main-content">
        Skip to content
      </a>
      <header className="msl-header">
        <div className="msl-wrap msl-nav">
          <Brand />
          <nav
            aria-label="Main navigation"
            className={`msl-links ${menuOpen ? 'is-open' : ''}`}
          >
            <a href="#product" onClick={() => setMenuOpen(false)}>
              The product
            </a>
            <a href="#trades" onClick={() => setMenuOpen(false)}>
              Who it’s for
            </a>
            <a href="#pricing" onClick={() => setMenuOpen(false)}>
              Pricing
            </a>
            <Link className="msl-mobile-login" to="/login">Log in</Link>
          </nav>
          <div className="msl-nav-actions">
            <Link className="msl-track" to="/customer-portal">
              Track a repair
            </Link>
            <Link className="msl-login" to="/login">
              Log in
            </Link>
            <Link className="msl-button msl-button-small" to="/signup">
              Start free trial <ArrowUpRight size={15} aria-hidden="true" />
            </Link>
            <button
              className="msl-menu"
              type="button"
              aria-label={menuOpen ? 'Close navigation' : 'Open navigation'}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(!menuOpen)}
            >
              {menuOpen ? <X /> : <Menu />}
            </button>
          </div>
        </div>
      </header>
      <main id="main-content">
        <section className="msl-hero">
          <div className="msl-wrap">
            <p className="msl-eyebrow">
              Repair shop software. Built around your working day.
            </p>
            <h1>
              Your repair shop,
              <br />
              <span>in good order.</span>
            </h1>
            <p className="msl-hero-copy">
              Manage watch repairs, shoe repairs and mobile locksmith jobs—from
              intake to invoice.
            </p>
            <div className="msl-hero-actions">
              <Link className="msl-button" to="/signup">
                Start your free trial{' '}
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
              <Link
                className="msl-button msl-button-outline"
                to="/login?demo=1"
              >
                Explore the demo <ArrowUpRight size={17} aria-hidden="true" />
              </Link>
            </div>
            <p className="msl-trial-note">
              14-day trial · From A$50/month · Card required for trial
            </p>
          </div>
          <div className="msl-wrap msl-product" id="product">
            <div className="msl-product-top">
              <div
                className="msl-tabs"
                role="tablist"
                aria-label="Explore Mainspring screens"
              >
                {screens.map((item, index) => (
                  <button
                    key={item.id}
                    ref={(el) => {
                      tabRefs.current[index] = el
                    }}
                    type="button"
                    role="tab"
                    id={`screen-tab-${item.id}`}
                    aria-controls="screen-panel"
                    aria-selected={screenIndex === index}
                    tabIndex={screenIndex === index ? 0 : -1}
                    onClick={() => setScreenIndex(index)}
                    onKeyDown={(event) => {
                      let next = index
                      if (event.key === 'ArrowRight')
                        next = (index + 1) % screens.length
                      else if (event.key === 'ArrowLeft')
                        next = (index - 1 + screens.length) % screens.length
                      else if (event.key === 'Home') next = 0
                      else if (event.key === 'End') next = screens.length - 1
                      else return
                      event.preventDefault()
                      setScreenIndex(next)
                      tabRefs.current[next]?.focus()
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <button
                className="msl-expand"
                aria-label={`Enlarge ${screen.label} screenshot`}
                type="button"
                onClick={() => setExpanded(true)}
              >
                <ZoomIn size={16} aria-hidden="true" />
                <span>Take a closer look</span>
              </button>
            </div>
            <div
              className="msl-screen-frame"
              id="screen-panel"
              role="tabpanel"
              aria-labelledby={`screen-tab-${screen.id}`}
              tabIndex={0}
            >
              <div className="msl-browser-bar" aria-hidden="true">
                <span />
                <span />
                <span />
                <p>mainspring.au</p>
              </div>
              <picture>
                <source media="(max-width: 540px)" srcSet={`/marketing/product/${screen.phoneImage}`} />
              <img
                key={screen.image}
                className="msl-product-screen"
                src={`/marketing/product/${screen.image}`}
                alt={screen.alt}
                width="1349"
                height="809"
                fetchPriority={screenIndex === 0 ? 'high' : 'auto'}
              />
              </picture>
            </div>
            <div className="msl-screen-caption">
              <p>{screen.description}</p>
              <span>Real Mainspring screens. Sample records.</span>
            </div>
          </div>
        </section>
        <section
          className="msl-trades msl-wrap"
          id="trades"
          aria-labelledby="trades-title"
        >
          <div className="msl-trades-intro">
            <p className="msl-eyebrow">Made for your trade</p>
            <h2 id="trades-title">
              At the counter.
              <br />
              On the bench.
              <br />
              Out on the road.
            </h2>
          </div>
          <div className="msl-trade">
            <Watch size={24} strokeWidth={1.5} aria-hidden="true" />
            <h3>Watch repairs</h3>
            <p>
              Keep watch details, service history, parts and repair progress on
              the ticket.
            </p>
            <Link to="/watch-repair-software">
              Watch repairs <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
          <div className="msl-trade">
            <Scissors size={24} strokeWidth={1.5} aria-hidden="true" />
            <h3>Shoe repairs</h3>
            <p>
              Book in multiple pairs, choose services and keep photos with the
              repair.
            </p>
            <Link to="/shoe-repair-software">
              Shoe repairs <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
          <div className="msl-trade">
            <KeyRound size={24} strokeWidth={1.5} aria-hidden="true" />
            <h3>Mobile locksmiths</h3>
            <p>
              Manage vehicle details, quotes, bookings and technicians from the
              same place.
            </p>
            <Link to="/mobile-services">
              Mobile services <ArrowRight size={15} aria-hidden="true" />
            </Link>
          </div>
        </section>
        <section className="msl-workflow" aria-labelledby="workflow-title">
          <div className="msl-wrap">
            <div className="msl-section-heading">
              <p className="msl-eyebrow">A place for every part of the job</p>
              <h2 id="workflow-title">
                From the first conversation
                <br />
                to the final invoice.
              </h2>
              <p>
                Keep the details with the work, so the next person
                <br className="msl-desktop-break" /> knows exactly where to pick
                up.
              </p>
            </div>
            <div className="msl-feature-row">
              <div className="msl-feature-visual">
                <ProductImage
                  name="repair-ticket.jpg"
                  alt="Actual Mainspring demo repair ticket with watch details, quote and repair status"
                />
              </div>
              <div className="msl-feature-copy">
                <span className="msl-feature-label">01 / The job</span>
                <h3>
                  Everything you need.
                  <br />
                  Right on the ticket.
                </h3>
                <p>
                  Customer details, the item, the work required and the latest
                  update. Find the history without searching through messages or
                  a paper diary.
                </p>
                <ul>
                  <li>
                    <Check />
                    Intake photos and job notes
                  </li>
                  <li>
                    <Check />
                    Clear repair stages and priorities
                  </li>
                  <li>
                    <Check />
                    Quotes and customer approvals
                  </li>
                </ul>
                <Link to="/login?demo=1">
                  Look around the demo{' '}
                  <ArrowRight size={17} aria-hidden="true" />
                </Link>
              </div>
            </div>
            <div className="msl-feature-row msl-feature-reverse">
              <div className="msl-feature-visual msl-visual-blue">
                <ProductImage name="invoices.jpg" alt={screens[2].alt} />
              </div>
              <div className="msl-feature-copy">
                <span className="msl-feature-label">02 / The paperwork</span>
                <h3>
                  Finish the work.
                  <br />
                  Keep the money in view.
                </h3>
                <p>
                  Follow the job through to invoicing, record payments and see
                  what’s still outstanding. Keep a clear record for the customer
                  and your business.
                </p>
                <ul>
                  <li>
                    <Check />
                    Linked jobs, quotes and invoices
                  </li>
                  <li>
                    <Check />
                    Paid and unpaid invoice views
                  </li>
                  <li>
                    <Check />
                    Reports across your service lines
                  </li>
                </ul>
                <a href="#pricing">
                  Find your plan <ArrowRight size={17} aria-hidden="true" />
                </a>
              </div>
            </div>
          </div>
        </section>
        <section
          className="msl-pricing msl-wrap"
          id="pricing"
          aria-labelledby="pricing-title"
        >
          <div className="msl-pricing-intro">
            <p className="msl-eyebrow">Straightforward pricing</p>
            <h2 id="pricing-title">
              A plan that fits
              <br />
              your shop.
            </h2>
            <p>
              Start with a 14-day trial.
              <br />
              Choose the plan for the way you work.
            </p>
            <Link to="/pricing">
              Full pricing details <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
          </div>
          <article className="msl-price-card">
            <span className="msl-plan-type">One location</span>
            <h3>Shop</h3>
            <p className="msl-price">
              A$50<span>/month</span>
            </p>
            <p className="msl-plan-description">
              Your day-to-day repair workspace.
            </p>
            <ul>
              <li>
                <Check />
                Watch, shoe and mobile services
              </li>
              <li>
                <Check />
                Customers and job management
              </li>
              <li>
                <Check />
                Quotes, invoices and reports
              </li>
              <li>
                <Check />
                Customer accounts
              </li>
            </ul>
            <Link className="msl-button msl-button-outline" to="/signup">
              Start your trial <ArrowRight size={17} aria-hidden="true" />
            </Link>
          </article>
          <article className="msl-price-card msl-price-pro">
            <span className="msl-plan-type">Multiple locations</span>
            <h3>Pro</h3>
            <p className="msl-price">
              A$90<span>/month</span>
            </p>
            <p className="msl-plan-description">
              Keep your locations connected.
            </p>
            <ul>
              <li>
                <Check />
                Everything in Shop
              </li>
              <li>
                <Check />
                Multi-site parent account
              </li>
              <li>
                <Check />
                Unlimited users and jobs
              </li>
              <li>
                <Check />
                Additional sites A$25/month each
              </li>
            </ul>
            <Link className="msl-button" to="/signup">
              Start your trial <ArrowRight size={17} aria-hidden="true" />
            </Link>
          </article>
          <p className="msl-pricing-note">
            Prices in Australian dollars. A card is required to start your
            trial. Billing begins after 14 days.
          </p>
        </section>
        <section className="msl-closing">
          <div className="msl-wrap">
            <div>
              <p className="msl-eyebrow">Meet your new working day</p>
              <h2>
                Make room for
                <br />
                the work you do best.
              </h2>
              <p>Give your repair business a clearer way to work.</p>
            </div>
            <div className="msl-closing-actions">
              <Link className="msl-button msl-button-white" to="/signup">
                Try Mainspring free <ArrowRight size={18} aria-hidden="true" />
              </Link>
              <Link to="/login?demo=1">
                Or take a look at the demo{' '}
                <ArrowUpRight size={15} aria-hidden="true" />
              </Link>
              <span>14 days · From A$50/month · Card required</span>
            </div>
          </div>
        </section>
      </main>
      <footer className="msl-footer msl-wrap">
        <div>
          <Brand />
          <p>Repair software for a well-run shop.</p>
        </div>
        <nav aria-label="Footer navigation">
          <a href="#pricing">Pricing</a>
          <Link to="/login">Log in</Link>
          <Link to="/customer-portal">Track a repair</Link>
          <Link to="/privacy">Privacy</Link>
          <Link to="/delete-account">Account deletion</Link>
        </nav>
        <p className="msl-copyright">© {new Date().getFullYear()} Mainspring</p>
      </footer>
      <dialog
        className="msl-lightbox"
        ref={dialogRef}
        onCancel={() => setExpanded(false)}
        onClick={(event) => {
          if (event.target === event.currentTarget) setExpanded(false)
        }}
        aria-label={`${screen.label} screenshot`}
      >
        <div className="msl-lightbox-header">
          <div>
            <strong>{screen.label}</strong>
            <span>Mainspring public demo · Sample records</span>
          </div>
          <button
            type="button"
            aria-label="Close screenshot"
            onClick={() => setExpanded(false)}
          >
            <X />
          </button>
        </div>
        <div className="msl-lightbox-viewport" tabIndex={0} aria-label="Scrollable product screenshot">
          <img
            src={`/marketing/product/${screen.image}`}
            alt={screen.alt}
            width="1349"
            height="809"
          />
        </div>
      </dialog>
    </div>
  )
}
