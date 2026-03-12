import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Menu, WatchIcon, X } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import Sidebar from './Sidebar'
import { Button, Modal } from '@/components/ui'
import { getDemoTourMode, getDemoTourStep, hasSeenPageTutorial, isDemoModeEnabled, setDemoTourMode, setDemoTourStep, setPageTutorialSeen } from '@/lib/onboarding'

type PageTutorial = {
  key: string
  title: string
  intro: string
  features: string[]
  nextStep: string
}

function getTutorialForPath(pathname: string): PageTutorial | null {
  if (pathname === '/dashboard') {
    return {
      key: 'dashboard',
      title: 'Dashboard Walkthrough',
      intro: 'This is your command center for what is happening in the workshop right now.',
      features: [
        'Live counters for jobs, customers, quotes, and invoices',
        'Status snapshots so you can see bottlenecks immediately',
        'Checklist guidance for first-time setup and launch tasks',
      ],
      nextStep: 'Start by opening Jobs to create or process today\'s repair work.',
    }
  }
  if (pathname === '/customers') {
    return {
      key: 'customers',
      title: 'Customers Page',
      intro: 'Use this page as your customer CRM for intake, communication, and history.',
      features: [
        'Create and search customer records quickly',
        'Open customer profiles with linked watches, shoes, and keys',
        'Keep contact notes for special handling and preferences',
      ],
      nextStep: 'Open any customer to create a new repair job directly from their profile.',
    }
  }
  if (/^\/customers\/[^/]+$/.test(pathname)) {
    return {
      key: 'customer-detail',
      title: 'Customer Profile',
      intro: 'This profile ties each person to all of their active and completed work.',
      features: [
        'View linked watches and repair history',
        'Start new watch, shoe, or auto-key jobs from one place',
        'Track notes and service context for future visits',
      ],
      nextStep: 'Create a job from this profile to keep records clean and connected.',
    }
  }
  if (pathname === '/jobs') {
    return {
      key: 'jobs-watch',
      title: 'Watch Repairs Board',
      intro: 'This page manages the full watch-repair pipeline from intake to collection.',
      features: [
        'Create jobs with priority, estimate, and deposit details',
        'Filter by status to run your bench workflow',
        'Move work through stages like quoting, parts, and completion',
      ],
      nextStep: 'Open a job to add quotes, status updates, and detailed work notes.',
    }
  }
  if (/^\/jobs\/[^/]+$/.test(pathname)) {
    return {
      key: 'job-watch-detail',
      title: 'Watch Job Detail',
      intro: 'This page is the full operational file for one watch repair.',
      features: [
        'Update status and add timeline notes for customer-facing tracking',
        'Attach media and intake evidence for condition records',
        'Create/send quotes and convert approved quotes into invoices',
      ],
      nextStep: 'Try a status update, then generate a quote to walk the full cycle.',
    }
  }
  if (pathname === '/shoe-repairs') {
    return {
      key: 'jobs-shoe',
      title: 'Shoe Repairs Board',
      intro: 'This board is tailored to shoe services and catalogue-based item selection.',
      features: [
        'Create jobs for soles, heels, stitching, and cleaning services',
        'Use catalogue items for consistent service naming and pricing',
        'Track shoe jobs from intake through collection',
      ],
      nextStep: 'Open one shoe job and append service items to build your estimate.',
    }
  }
  if (/^\/shoe-repairs\/[^/]+$/.test(pathname)) {
    return {
      key: 'job-shoe-detail',
      title: 'Shoe Job Detail',
      intro: 'This page tracks every operation for a single shoe repair order.',
      features: [
        'Review selected catalogue work items and costs',
        'Update progress and communicate expected pickup timing',
        'Store photos and notes for before/after verification',
      ],
      nextStep: 'Add an item and push the status to test your intake-to-delivery flow.',
    }
  }
  if (pathname === '/auto-key') {
    return {
      key: 'jobs-auto-key',
      title: 'Auto Key Jobs Board',
      intro: 'This board handles vehicle key cutting, programming, and handover tracking.',
      features: [
        'Create jobs with vehicle, key type, and quantity details',
        'Track programming status separately from commercial status',
        'Manage quote, deposit, and cost visibility per job',
      ],
      nextStep: 'Open a key job and update programming status to see progress controls.',
    }
  }
  if (/^\/auto-key\/[^/]+$/.test(pathname)) {
    return {
      key: 'job-auto-key-detail',
      title: 'Auto Key Job Detail',
      intro: 'This page is your technical worksheet plus customer transaction record.',
      features: [
        'Capture VIN, plate, make/model, and key specifications',
        'Update programming checkpoints and workshop notes',
        'Prepare quote/invoice actions tied to this key job',
      ],
      nextStep: 'Update programming state, then test a quote-to-payment path.',
    }
  }
  if (pathname === '/quotes') {
    return {
      key: 'quotes',
      title: 'Quotes Workspace',
      intro: 'Use quotes to convert diagnostics into approved repair authorizations.',
      features: [
        'Draft labor/parts/fees with tax and total calculations',
        'Send quotes with approval links for fast customer response',
        'Track approved, declined, and pending quote outcomes',
      ],
      nextStep: 'Send one quote and open its approval page to test the customer view.',
    }
  }
  if (pathname === '/invoices') {
    return {
      key: 'invoices',
      title: 'Invoices & Payments',
      intro: 'This page converts approved work into payable records and receipt flow.',
      features: [
        'Review invoice totals and payment status',
        'Record partial or full payments against outstanding balances',
        'Print invoices for in-store pickup and records',
      ],
      nextStep: 'Open an invoice and record a payment to close the loop.',
    }
  }
  if (pathname === '/reports') {
    return {
      key: 'reports',
      title: 'Reports & Trends',
      intro: 'This page gives operational and financial visibility across your tenant.',
      features: [
        'Core KPIs for volume, margin, and throughput',
        'Monthly trend bars for jobs opened and revenue',
        'Tenant audit feed showing key account events',
      ],
      nextStep: 'Use trend and audit sections to spot workflow and staffing pressure points.',
    }
  }
  if (pathname === '/database') {
    return {
      key: 'database',
      title: 'Database Tools',
      intro: 'Use this area for data operations, backups, and controlled imports.',
      features: [
        'Inspect data health and import pathways',
        'Support safe CSV-based migration into live workflows',
        'Prepare records for reporting and historical analysis',
      ],
      nextStep: 'Review your import options before loading external datasets.',
    }
  }
  if (pathname === '/accounts') {
    return {
      key: 'accounts',
      title: 'Accounts & Billing',
      intro: 'This page controls team access, permissions, plan, and usage visibility.',
      features: [
        'Add team users and set operational roles',
        'Switch plan bundles per tenant scope',
        'Monitor plan usage with billing thresholds and portal link',
      ],
      nextStep: 'Add a test staff account, then verify role permissions in workflow pages.',
    }
  }
  if (pathname === '/customer-accounts') {
    return {
      key: 'customer-accounts',
      title: 'Customer Accounts (B2B)',
      intro: 'Manage business clients with account-level billing and linked jobs.',
      features: [
        'Create and maintain business account entities',
        'Attach repair work to customer accounts for invoicing',
        'Improve visibility for recurring trade clients',
      ],
      nextStep: 'Create one B2B account and attach a job to it for testing.',
    }
  }
  if (pathname === '/parent-account') {
    return {
      key: 'parent-account',
      title: 'Multi-Site Parent Account',
      intro: 'This page is your headquarters-level control for linked sites.',
      features: [
        'Link and manage multiple tenant sites under one owner',
        'Review parent-account activity and site operations',
        'Switch active site context without logging out',
      ],
      nextStep: 'Link a second site and test switching from the active-site selector.',
    }
  }

  return null
}

const GUIDED_TOUR_PATHS = [
  '/dashboard',
  '/customers',
  '/jobs',
  '/shoe-repairs',
  '/auto-key',
  '/quotes',
  '/invoices',
  '/reports',
  '/accounts',
]

const GUIDED_TOUR_LABELS: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/customers': 'Customers',
  '/jobs': 'Watch Repairs',
  '/shoe-repairs': 'Shoe Repairs',
  '/auto-key': 'Auto Key',
  '/quotes': 'Quotes',
  '/invoices': 'Invoices',
  '/reports': 'Reports',
  '/accounts': 'Accounts',
}

export default function AppShell() {
  const { token, initializing, activeSiteTenantId, availableSites, switchSite } = useAuth()
  const location = useLocation()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [switchingSite, setSwitchingSite] = useState(false)
  const navigate = useNavigate()
  const [activeTutorial, setActiveTutorial] = useState<PageTutorial | null>(null)
  const [showWelcomeModal, setShowWelcomeModal] = useState(false)
  const [tourMode, setTourMode] = useState<'self' | 'guided' | null>(() =>
    isDemoModeEnabled() ? getDemoTourMode() : null
  )
  const [guidedStep, setGuidedStep] = useState(() =>
    isDemoModeEnabled() ? getDemoTourStep() : 0
  )

  useEffect(() => {
    if (!token) return
    if (!isDemoModeEnabled()) return

    const currentMode = getDemoTourMode()

    // No mode chosen yet — show welcome modal on first dashboard visit
    if (currentMode === null) {
      if (location.pathname === '/dashboard') setShowWelcomeModal(true)
      return
    }

    // Guided tour — keep step in sync with current path
    if (currentMode === 'guided') {
      const stepIndex = GUIDED_TOUR_PATHS.indexOf(location.pathname)
      if (stepIndex !== -1) {
        setGuidedStep(stepIndex)
        setDemoTourStep(stepIndex)
      }
      setTourMode('guided')
      setActiveTutorial(null)
      return
    }

    // Self-guided — show page tutorial popup
    setTourMode('self')
    const tutorial = getTutorialForPath(location.pathname)
    if (!tutorial) { setActiveTutorial(null); return }
    if (hasSeenPageTutorial(activeSiteTenantId, tutorial.key)) { setActiveTutorial(null); return }
    setActiveTutorial(tutorial)
  }, [activeSiteTenantId, location.pathname, token])

  function dismissTutorial() {
    if (activeTutorial) {
      setPageTutorialSeen(activeSiteTenantId, activeTutorial.key, true)
    }
    setActiveTutorial(null)
  }

  function chooseMode(mode: 'self' | 'guided') {
    setDemoTourMode(mode)
    setTourMode(mode)
    setShowWelcomeModal(false)
    if (mode === 'guided') {
      setGuidedStep(0)
      setDemoTourStep(0)
      navigate('/dashboard')
    }
  }

  function advanceGuidedTour() {
    const next = guidedStep + 1
    if (next >= GUIDED_TOUR_PATHS.length) {
      setDemoTourMode(null)
      setTourMode(null)
      return
    }
    setGuidedStep(next)
    setDemoTourStep(next)
    navigate(GUIDED_TOUR_PATHS[next])
  }

  function retreatGuidedTour() {
    const prev = guidedStep - 1
    if (prev < 0) return
    setGuidedStep(prev)
    setDemoTourStep(prev)
    navigate(GUIDED_TOUR_PATHS[prev])
  }

  function exitGuidedTour() {
    setDemoTourMode(null)
    setTourMode(null)
  }

  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)' }}>
        Preparing test session...
      </div>
    )
  }

  if (!token) {
    return <Navigate to="/" replace />
  }

  const guidedCurrentTutorial = tourMode === 'guided'
    ? getTutorialForPath(GUIDED_TOUR_PATHS[guidedStep] ?? '')
    : null
  const guidedIsLast = guidedStep >= GUIDED_TOUR_PATHS.length - 1
  const guidedNextLabel = !guidedIsLast ? GUIDED_TOUR_LABELS[GUIDED_TOUR_PATHS[guidedStep + 1]] : null

  return (
    <div className="h-screen md:flex" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <Sidebar className="hidden md:flex" />

      <div className="flex min-w-0 flex-1 flex-col">
        <header
          className="md:hidden sticky top-0 z-20 flex items-center justify-between px-4 py-3"
          style={{ backgroundColor: 'var(--cafe-surface)', borderBottom: '1px solid var(--cafe-border)' }}
        >
          <button
            onClick={() => setMobileNavOpen(true)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg"
            style={{ color: 'var(--cafe-text-mid)' }}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>

          <div className="flex items-center gap-2">
            <div
              className="h-7 w-7 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'var(--cafe-espresso-2)', color: 'var(--cafe-gold)' }}
            >
              <WatchIcon size={14} strokeWidth={2.5} />
            </div>
            <span style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }} className="text-base font-semibold">
              Mainspring
            </span>
          </div>

          <span className="w-9" />
        </header>

        <main className={`flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6 md:px-8 md:py-8${tourMode === 'guided' ? ' pb-28' : ''}`}>
          {availableSites.length > 1 && (
            <div className="mb-4 flex items-center justify-end gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>
                Active site
              </span>
              <select
                value={activeSiteTenantId ?? ''}
                disabled={switchingSite}
                onChange={async (e) => {
                  const nextTenantId = e.target.value
                  if (!nextTenantId || nextTenantId === activeSiteTenantId) return
                  setSwitchingSite(true)
                  try {
                    await switchSite(nextTenantId)
                  } finally {
                    setSwitchingSite(false)
                  }
                }}
                className="rounded-lg px-2.5 py-2 text-xs"
                style={{
                  backgroundColor: 'var(--cafe-surface)',
                  border: '1px solid var(--cafe-border-2)',
                  color: 'var(--cafe-text)',
                }}
              >
                {availableSites.map(site => (
                  <option key={site.tenant_id} value={site.tenant_id}>{site.tenant_name}</option>
                ))}
              </select>
            </div>
          )}
          <Outlet />
        </main>
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            className="absolute inset-0"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.35)' }}
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation overlay"
          />

          <div className="relative h-full w-[84vw] max-w-72">
            <Sidebar
              mobile
              className="h-full"
              onNavigate={() => setMobileNavOpen(false)}
              onClose={() => setMobileNavOpen(false)}
              closeIcon={<X size={18} />}
            />
          </div>
        </div>
      )}

      {/* Welcome modal — choose between self-guided and in-depth tour */}
      {showWelcomeModal && (
        <Modal title="👋 Welcome to the Mainspring Demo!" onClose={() => chooseMode('self')}>
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
              Your demo workspace is ready — real jobs, customers, and records are pre-loaded.
              How would you like to explore?
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <button
                onClick={() => chooseMode('self')}
                className="rounded-xl p-4 text-left hover:opacity-90 transition-opacity"
                style={{ backgroundColor: 'var(--cafe-surface)', border: '2px solid var(--cafe-border-2)' }}
              >
                <div className="text-2xl mb-2">🧭</div>
                <div className="font-semibold mb-1" style={{ color: 'var(--cafe-text)' }}>Self-Guided</div>
                <div className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
                  Explore freely at your own pace. A tip pop-up explains each page as you navigate to it.
                </div>
              </button>
              <button
                onClick={() => chooseMode('guided')}
                className="rounded-xl p-4 text-left hover:opacity-90 transition-opacity"
                style={{ backgroundColor: 'var(--cafe-espresso-2)', border: '2px solid var(--cafe-gold)' }}
              >
                <div className="text-2xl mb-2">🎯</div>
                <div className="font-semibold mb-1" style={{ color: 'var(--cafe-gold)' }}>In-Depth Tour</div>
                <div className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
                  We walk you through every feature in sequence. Click Next to advance through all 9 sections.
                </div>
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Self-guided page tutorial popup */}
      {activeTutorial && (
        <Modal title={activeTutorial.title} onClose={dismissTutorial}>
          <div className="space-y-3 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
            <p style={{ color: 'var(--cafe-text)' }}>{activeTutorial.intro}</p>
            <p className="font-semibold" style={{ color: 'var(--cafe-text)' }}>This page lets you:</p>
            <ul className="list-disc pl-5 space-y-1">
              {activeTutorial.features.map(item => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <p style={{ color: 'var(--cafe-text)' }}>
              <span className="font-semibold">Suggested next step:</span> {activeTutorial.nextStep}
            </p>
            <div className="pt-1 flex gap-2">
              <Button variant="secondary" className="flex-1" onClick={dismissTutorial}>Got it</Button>
              <Button className="flex-1" onClick={dismissTutorial}>Continue</Button>
            </div>
          </div>
        </Modal>
      )}

      {/* In-depth guided tour bar — fixed at bottom */}
      {tourMode === 'guided' && !showWelcomeModal && (
        <div
          className="fixed bottom-0 left-0 right-0 z-50"
          style={{
            backgroundColor: 'var(--cafe-espresso-2)',
            borderTop: '2px solid var(--cafe-gold)',
            boxShadow: '0 -4px 24px rgba(0,0,0,0.4)',
          }}
        >
          {/* Progress bar */}
          <div className="h-1" style={{ backgroundColor: 'var(--cafe-border)' }}>
            <div
              className="h-1 transition-all duration-300"
              style={{
                backgroundColor: 'var(--cafe-gold)',
                width: `${((guidedStep + 1) / GUIDED_TOUR_PATHS.length) * 100}%`,
              }}
            />
          </div>
          <div className="px-4 py-3 sm:px-6">
            <div className="flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--cafe-gold)' }}>
                    Step {guidedStep + 1} of {GUIDED_TOUR_PATHS.length}
                  </span>
                  <span className="text-xs font-medium" style={{ color: 'var(--cafe-text-mid)' }}>
                    — {GUIDED_TOUR_LABELS[GUIDED_TOUR_PATHS[guidedStep]]}
                  </span>
                </div>
                {guidedCurrentTutorial && (
                  <p className="text-sm line-clamp-2" style={{ color: 'var(--cafe-text-muted)' }}>
                    {guidedCurrentTutorial.intro}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                {guidedStep > 0 && (
                  <button
                    onClick={retreatGuidedTour}
                    className="px-3 py-1.5 rounded-lg text-sm font-medium"
                    style={{
                      backgroundColor: 'var(--cafe-surface)',
                      color: 'var(--cafe-text-mid)',
                      border: '1px solid var(--cafe-border-2)',
                    }}
                  >
                    ← Back
                  </button>
                )}
                <button
                  onClick={exitGuidedTour}
                  className="px-3 py-1.5 rounded-lg text-sm"
                  style={{ color: 'var(--cafe-text-muted)' }}
                >
                  Exit Tour
                </button>
                <button
                  onClick={advanceGuidedTour}
                  className="px-4 py-1.5 rounded-lg text-sm font-bold"
                  style={{
                    backgroundColor: 'var(--cafe-gold)',
                    color: 'var(--cafe-espresso-1)',
                  }}
                >
                  {guidedIsLast ? '🎉 Finish Tour' : `Next: ${guidedNextLabel} →`}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
