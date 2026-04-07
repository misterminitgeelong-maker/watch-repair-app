import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Menu, WatchIcon, X } from 'lucide-react'
import {
  listAutoKeyJobs,
  listCustomers,
  listInvoices,
  listJobs,
  listQuotes,
  listShoeRepairJobs,
} from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import Sidebar from './Sidebar'
import { Button, Modal } from '@/components/ui'
import {
  getDemoTourMode,
  getDemoTourStep,
  hasSeenPageTutorial,
  isDemoModeEnabled,
  setDemoTourMode,
  setDemoTourStep,
  setPageTutorialSeen,
} from '@/lib/onboarding'
import { isAutoKeyJobDetailPath } from '@/components/MobileServicesSubNav'

type PageTutorial = {
  key: string
  title: string
  intro: string
  features: string[]
  nextStep: string
}

type GuidedTourStep = {
  key: string
  title: string
  label: string
  routePath: string
  matcher: (pathname: string) => boolean
  intro: string
  task: string
  highlights: string[]
  actionLabel?: string
  actionPath?: string
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
        'Start new watch, shoe, or mobile services jobs from one place',
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
      title: 'Mobile Services Board',
      intro: 'This board handles vehicle key cutting, programming, mobile/shop jobs, and handover tracking.',
      features: [
        'Create jobs with vehicle, key type, and quantity details',
        'Track programming status separately from commercial status',
        'Manage quote, deposit, and cost visibility per job',
      ],
      nextStep: 'Open a key job and update programming status to see progress controls.',
    }
  }
  if (isAutoKeyJobDetailPath(pathname)) {
    return {
      key: 'job-auto-key-detail',
      title: 'Mobile Services Job Detail',
      intro: 'This page is your technical worksheet plus customer transaction record.',
      features: [
        'Capture VIN, plate, make/model, and key specifications',
        'Update programming checkpoints and workshop notes',
        'Prepare quote/invoice actions tied to this key job',
      ],
      nextStep: 'Update programming state, then test a quote-to-payment path.',
    }
  }
  if (pathname === '/auto-key/team') {
    return {
      key: 'mobile-team',
      title: 'Mobile Services Team',
      intro: 'See who can be assigned to mobile jobs, add technicians, and open commission rules.',
      features: ['Roster of technician logins', 'Add technician (owners)', 'Commission rules per tech (owners and managers)'],
      nextStep: 'Add a technician if needed, then assign them from a job or dispatch view.',
    }
  }
  if (pathname === '/auto-key/prospects') {
    return {
      key: 'mobile-prospects',
      title: 'Mobile Services Prospects',
      intro: 'Search and shortlist businesses by category and geography for B2B outreach.',
      features: ['Filter by trade category and state', 'Drill into suburbs before running a search', 'Optional live Places-backed search when configured'],
      nextStep: 'Pick a category and state, then run a prospect search.',
    }
  }
  if (pathname === '/auto-key/toolkit') {
    return {
      key: 'mobile-toolkit',
      title: 'Mobile Services Toolkit',
      intro: 'Track what you carry on the van and sanity-check scenarios before a job.',
      features: ['Tick tools by group', 'Save your default kit per technician login', 'Run scenario checks for gaps and substitutes'],
      nextStep: 'Save your tools, then try a scenario recommendation.',
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
  if (/^\/invoices\/[^/]+$/.test(pathname)) {
    return {
      key: 'invoice-detail',
      title: 'Invoice Detail',
      intro: 'This is the financial handoff page for a completed or approved piece of work.',
      features: [
        'Review the invoice status and totals in one place',
        'Record payment directly from the invoice',
        'Print a clean customer-facing invoice or PDF',
      ],
      nextStep: 'Record a payment here when the customer settles up.',
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

function exactMatcher(path: string) {
  return (pathname: string) => pathname === path
}

export default function AppShell() {
  const {
    token,
    initializing,
    activeSiteTenantId,
    availableSites,
    switchSite,
    hasFeature,
    sessionReady,
    signupPaymentPending,
    role,
    planCode,
  } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const demoModeEnabled = isDemoModeEnabled()

  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [switchingSite, setSwitchingSite] = useState(false)
  const [activeTutorial, setActiveTutorial] = useState<PageTutorial | null>(null)
  const [showWelcomeModal, setShowWelcomeModal] = useState(false)
  const [showGuidedModal, setShowGuidedModal] = useState(false)
  const [lastGuidedModalKey, setLastGuidedModalKey] = useState<string | null>(null)
  const [tourMode, setTourMode] = useState<'self' | 'guided' | null>(() =>
    demoModeEnabled ? getDemoTourMode() : null,
  )
  const [guidedStep, setGuidedStep] = useState(() =>
    demoModeEnabled ? getDemoTourStep() : 0,
  )
  const guidedTourDataEnabled = demoModeEnabled && (tourMode === 'guided' || showGuidedModal || showWelcomeModal)

  const { data: customers } = useQuery({
    queryKey: ['customers', 'guided-tour'],
    queryFn: () => listCustomers().then((r) => r.data),
    enabled: guidedTourDataEnabled,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })
  const { data: jobs } = useQuery({
    queryKey: ['jobs', 'guided-tour'],
    queryFn: () => listJobs().then((r) => r.data),
    enabled: guidedTourDataEnabled,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })
  const { data: shoeJobs } = useQuery({
    queryKey: ['shoe-repair-jobs', 'guided-tour'],
    queryFn: () => listShoeRepairJobs().then((r) => r.data),
    enabled: guidedTourDataEnabled && hasFeature('shoe'),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })
  const { data: autoKeyJobs } = useQuery({
    queryKey: ['auto-key-jobs', 'guided-tour'],
    queryFn: () => listAutoKeyJobs().then((r) => r.data),
    enabled: guidedTourDataEnabled && hasFeature('auto_key'),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })
  const { data: quotes } = useQuery({
    queryKey: ['quotes', 'guided-tour'],
    queryFn: () => listQuotes().then((r) => r.data),
    enabled: guidedTourDataEnabled,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })
  const { data: invoices } = useQuery({
    queryKey: ['invoices', 'guided-tour'],
    queryFn: () => listInvoices().then((r) => r.data),
    enabled: guidedTourDataEnabled,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })

  const guidedTourSteps = useMemo<GuidedTourStep[]>(() => {
    const firstCustomer = customers?.[0]
    const firstWatchJob = jobs?.[0]
    const firstShoeJob = shoeJobs?.[0]
    const firstAutoKeyJob = autoKeyJobs?.[0]
    const firstInvoice = invoices?.[0]
    const firstQuote = quotes?.[0]

    const customerDetailPath = firstCustomer ? `/customers/${firstCustomer.id}` : '/customers'
    const watchJobDetailPath = firstWatchJob ? `/jobs/${firstWatchJob.id}` : '/jobs'
    const shoeJobDetailPath = firstShoeJob ? `/shoe-repairs/${firstShoeJob.id}` : '/shoe-repairs'
    const autoKeyDetailPath = firstAutoKeyJob ? `/auto-key/${firstAutoKeyJob.id}` : '/auto-key'
    const invoiceDetailPath = firstInvoice ? `/invoices/${firstInvoice.id}` : '/invoices'

    const shoeItemsPreview = firstShoeJob?.items.slice(0, 2).map((item) => item.item_name).join(' and ')
    const watchJobLabel = firstWatchJob ? `Open watch job #${firstWatchJob.job_number}` : 'Open a watch repair'
    const shoeJobLabel = firstShoeJob ? `Open shoe job #${firstShoeJob.job_number}` : 'Open a shoe repair'
    const autoKeyLabel = firstAutoKeyJob ? `Open job #${firstAutoKeyJob.job_number}` : 'Open a Mobile Services job'
    const quoteLabel = firstQuote ? 'Go to quotes in progress' : 'Go to quotes'
    const invoiceLabel = firstInvoice ? `Open invoice #${firstInvoice.invoice_number}` : 'Go to invoices'

    const steps: GuidedTourStep[] = [
      {
        key: 'guided-dashboard',
        title: 'Start on the live dashboard',
        label: 'Dashboard',
        routePath: '/dashboard',
        matcher: exactMatcher('/dashboard'),
        intro: 'This is the best opening view for a demo because it shows the health of the whole workshop at once.',
        task: 'Take a quick look at the KPI row, then jump into a real customer record.',
        highlights: [
          'The dashboard pulls together customers, jobs, quotes, invoices, billing, and reports.',
          'This is where an owner or manager sees pressure points before drilling into detail.',
        ],
        actionLabel: 'Take me to customers',
        actionPath: '/customers',
      },
      {
        key: 'guided-customers-list',
        title: 'Customers are the hub of the workflow',
        label: 'Customers',
        routePath: '/customers',
        matcher: exactMatcher('/customers'),
        intro: 'Every repair starts with the customer. This list is the CRM layer for the business.',
        task: 'Open a demo customer so you can see how repairs stay connected to the person.',
        highlights: [
          'You can search the entire customer book quickly during intake.',
          'Each profile becomes the anchor for watch, shoe, and key work.',
        ],
        actionLabel: firstCustomer ? `Open ${firstCustomer.full_name}` : 'Open a demo customer',
        actionPath: customerDetailPath,
      },
      {
        key: 'guided-customer-detail',
        title: 'A customer profile brings the history together',
        label: 'Customer profile',
        routePath: customerDetailPath,
        matcher: (pathname: string) => /^\/customers\/[^/]+$/.test(pathname),
        intro: 'This is where staff see prior work, contact context, and what is currently live for that customer.',
        task: 'Jump into a real watch repair from here so the demo feels connected rather than abstract.',
        highlights: [
          'The customer profile reduces duplicate records and keeps job history easy to follow.',
          'In a real intake flow, this is where a returning client gets recognized instantly.',
        ],
        actionLabel: watchJobLabel,
        actionPath: watchJobDetailPath,
      },
      {
        key: 'guided-watch-list',
        title: 'The watch repair board is the main operational queue',
        label: 'Watch repairs',
        routePath: '/jobs',
        matcher: exactMatcher('/jobs'),
        intro: 'This board lets the team filter, process, and prioritize bench work throughout the day.',
        task: 'Open one real job so you can see the actual repair workflow screen.',
        highlights: [
          'Statuses map to the real bench lifecycle: quote, approval, parts, service, completion, collection.',
          'This is the page most techs and intake staff live in during the day.',
        ],
        actionLabel: watchJobLabel,
        actionPath: watchJobDetailPath,
      },
      {
        key: 'guided-watch-detail',
        title: 'This job detail page is where the work actually happens',
        label: 'Watch repair detail',
        routePath: watchJobDetailPath,
        matcher: (pathname: string) => /^\/jobs\/[^/]+$/.test(pathname),
        intro: 'On a real repair, this screen drives the customer-facing timeline and the workshop actions.',
        task: 'Notice the status controls, notes, attachments, and quote flow. Then switch to shoe repairs for a different service type.',
        highlights: [
          'This page supports quote creation, status changes, and intake evidence in one place.',
          'It is designed to avoid fragmented tools or off-system notes.',
        ],
        actionLabel: 'Show me shoe repairs',
        actionPath: '/shoe-repairs',
      },
      {
        key: 'guided-shoe-list',
        title: 'Shoe repairs feel different because the workflow is catalogue-based',
        label: 'Shoe repairs',
        routePath: '/shoe-repairs',
        matcher: exactMatcher('/shoe-repairs'),
        intro: 'This area is tuned for shoe work rather than watch service, so the demo should show that difference clearly.',
        task: 'Open one shoe repair and look at the selected service items instead of just a generic repair title.',
        highlights: [
          'The catalogue keeps pricing and naming consistent across repeated shoe services.',
          'This makes quoting faster at the counter and cleaner for the customer.',
        ],
        actionLabel: shoeJobLabel,
        actionPath: shoeJobDetailPath,
      },
      {
        key: 'guided-shoe-detail',
        title: 'This shoe repair shows the service-item workflow',
        label: 'Shoe repair detail',
        routePath: shoeJobDetailPath,
        matcher: (pathname: string) => /^\/shoe-repairs\/[^/]+$/.test(pathname),
        intro: 'Instead of a vague job note, shoe repairs can carry a structured list of service items and costs.',
        task: `Look at the service items${shoeItemsPreview ? ` like ${shoeItemsPreview}` : ''} and imagine how easy it is to explain the work to a customer at pickup.`,
        highlights: [
          'This gives the demo a tactile feel because the service mix is visible, not hidden.',
          'It is a strong differentiator when showing the app to repair businesses with multiple service types.',
        ],
        actionLabel: 'Take me to Mobile Services',
        actionPath: '/auto-key',
      },
      {
        key: 'guided-auto-list',
        title: 'Mobile Services has its own technical flow',
        label: 'Mobile Services',
        routePath: '/auto-key',
        matcher: exactMatcher('/auto-key'),
        intro: 'Vehicle jobs need a different data model, so this queue is tailored to key programming and vehicle details.',
        task: 'Open one of the demo key jobs to see the technical fields and programming state.',
        highlights: [
          'The programming status sits alongside the commercial job status.',
          'That split makes the workflow clearer for technicians and front-desk staff.',
        ],
        actionLabel: autoKeyLabel,
        actionPath: autoKeyDetailPath,
      },
      {
        key: 'guided-auto-detail',
        title: 'The Mobile Services detail page shows why this is not just another repair template',
        label: 'Mobile Services detail',
        routePath: autoKeyDetailPath,
        matcher: (pathname: string) => isAutoKeyJobDetailPath(pathname),
        intro: 'VINs, plates, key type, and programming steps matter here, so the app gives that work its own structure.',
        task: 'Take note of the vehicle-specific fields, then move into the commercial side of the process with quotes.',
        highlights: [
          'This step helps prospects see the app covers more than one repair vertical well.',
          'The same customer and billing system still wraps around the technical workflow.',
        ],
        actionLabel: quoteLabel,
        actionPath: '/quotes',
      },
      {
        key: 'guided-quotes',
        title: 'Quotes convert diagnostics into approvals',
        label: 'Quotes',
        routePath: '/quotes',
        matcher: exactMatcher('/quotes'),
        intro: 'This workspace is where quoted work becomes an approved commercial job instead of just a note in the system.',
        task: 'Look at how quotes link back to the job, then open an invoice to see the handoff after approval.',
        highlights: [
          'Quotes can be created from active jobs and sent for customer approval.',
          'The approval flow is what connects workshop diagnostics to cash flow.',
        ],
        actionLabel: invoiceLabel,
        actionPath: invoiceDetailPath,
      },
      {
        key: 'guided-invoice-detail',
        title: 'Invoices close the loop from approved work to payment',
        label: 'Invoice detail',
        routePath: invoiceDetailPath,
        matcher: (pathname: string) => /^\/invoices\/[^/]+$/.test(pathname),
        intro: 'This is the handoff point where approved work becomes a payable customer record.',
        task: 'Look at the totals and payment action, then jump to reports to see the bigger commercial picture.',
        highlights: [
          'The invoice is customer-facing but still linked back to the operational work.',
          'This is the clearest place to explain how the app helps with both workshop flow and revenue collection.',
        ],
        actionLabel: 'Show me the reports',
        actionPath: '/reports',
      },
      {
        key: 'guided-reports',
        title: 'Reports turn the day-to-day workflow into business insight',
        label: 'Reports',
        routePath: '/reports',
        matcher: exactMatcher('/reports'),
        intro: 'This page proves the app is not only an operations tool; it also gives the owner visibility into performance.',
        task: 'Scan the KPIs and trend blocks, then finish in Accounts where permissions and plan usage are managed.',
        highlights: [
          'Reports show revenue, margin, approval rates, and activity history.',
          'That makes the product feel like a business system, not only a job tracker.',
        ],
        actionLabel: 'Finish in Accounts',
        actionPath: '/accounts',
      },
      {
        key: 'guided-accounts',
        title: "You've seen the full workflow",
        label: 'Accounts',
        routePath: '/accounts',
        matcher: exactMatcher('/accounts'),
        intro: "You've seen the full workflow — from intake and quotes to invoices, reports, and account control.",
        task: 'Review users, plan bundles, and billing usage here, or start your own shop to use Mainspring for real.',
        highlights: [
          'You can show team setup, roles, and billing limits without leaving the app.',
          'That closes the story: intake, production, approval, payment, reporting, and account control.',
        ],
        actionLabel: 'Start your shop →',
        actionPath: '/signup',
      },
    ]

    return steps.filter((step) => {
      if (step.label === 'Shoe repairs' || step.label === 'Shoe repair detail') return hasFeature('shoe')
      if (step.label === 'Mobile Services' || step.label === 'Mobile Services detail') return hasFeature('auto_key')
      return true
    })
  }, [autoKeyJobs, customers, hasFeature, invoices, jobs, quotes, shoeJobs])

  const currentGuidedStepIndex = useMemo(
    () => guidedTourSteps.findIndex((step) => step.matcher(location.pathname)),
    [guidedTourSteps, location.pathname],
  )

  const currentGuidedStep = currentGuidedStepIndex >= 0
    ? guidedTourSteps[currentGuidedStepIndex]
    : guidedTourSteps[guidedStep] ?? null

  useEffect(() => {
    if (!token) return
    if (!demoModeEnabled) return

    const currentMode = getDemoTourMode()

    if (currentMode === null) {
      if (location.pathname === '/dashboard') setShowWelcomeModal(true)
      return
    }

    if (currentMode === 'guided') {
      if (currentGuidedStepIndex !== -1) {
        setGuidedStep(currentGuidedStepIndex)
        setDemoTourStep(currentGuidedStepIndex)
      }
      setTourMode('guided')
      setActiveTutorial(null)
      return
    }

    setTourMode('self')
    const tutorial = getTutorialForPath(location.pathname)
    if (!tutorial) {
      setActiveTutorial(null)
      return
    }
    if (hasSeenPageTutorial(activeSiteTenantId, tutorial.key)) {
      setActiveTutorial(null)
      return
    }
    setActiveTutorial(tutorial)
  }, [activeSiteTenantId, currentGuidedStepIndex, demoModeEnabled, location.pathname, token])

  useEffect(() => {
    if (tourMode !== 'guided' || !currentGuidedStep) {
      setShowGuidedModal(false)
      return
    }
    if (currentGuidedStep.key !== lastGuidedModalKey) {
      setShowGuidedModal(true)
      setLastGuidedModalKey(currentGuidedStep.key)
    }
  }, [currentGuidedStep, lastGuidedModalKey, tourMode])

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
    setLastGuidedModalKey(null)
    if (mode === 'guided') {
      setGuidedStep(0)
      setDemoTourStep(0)
      navigate(guidedTourSteps[0]?.routePath ?? '/dashboard')
    }
  }

  function goToGuidedStep(index: number) {
    const step = guidedTourSteps[index]
    if (!step) return
    setGuidedStep(index)
    setDemoTourStep(index)
    navigate(step.routePath)
  }

  function advanceGuidedTour() {
    const next = guidedStep + 1
    if (next >= guidedTourSteps.length) {
      setDemoTourMode(null)
      setTourMode(null)
      setShowGuidedModal(false)
      return
    }
    goToGuidedStep(next)
  }

  function retreatGuidedTour() {
    const prev = guidedStep - 1
    if (prev < 0) return
    goToGuidedStep(prev)
  }

  function exitGuidedTour() {
    setDemoTourMode(null)
    setTourMode(null)
    setShowGuidedModal(false)
  }

  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)' }}>
        Loading...
      </div>
    )
  }

  if (!token) {
    return <Navigate to="/" replace />
  }

  if (sessionReady && signupPaymentPending && role !== 'platform_admin' && location.pathname !== '/subscription-required') {
    return <Navigate to={`/subscription-required?plan=${encodeURIComponent(planCode)}`} replace />
  }

  if (location.pathname === '/subscription-required') {
    return (
      <div className="min-h-screen" style={{ backgroundColor: 'var(--cafe-bg)' }}>
        <Outlet />
      </div>
    )
  }

  const guidedIsLast = guidedStep >= guidedTourSteps.length - 1
  const guidedNextLabel = !guidedIsLast ? guidedTourSteps[guidedStep + 1]?.label : null

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
            className="inline-flex h-11 min-w-11 items-center justify-center rounded-lg -ml-1"
            style={{ color: 'var(--cafe-text-mid)' }}
            aria-label="Open navigation"
          >
            <Menu size={22} />
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
                {availableSites.map((site) => (
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

      {showWelcomeModal && (
        <Modal title="Welcome to the Mainspring Demo" onClose={() => chooseMode('self')}>
          <div className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
              Your demo workspace is ready with real sample records. Choose whether you want to explore freely or be walked through the product with live demo jobs and customer records.
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <button
                onClick={() => chooseMode('self')}
                className="rounded-xl p-4 text-left hover:opacity-90 transition-opacity"
                style={{ backgroundColor: 'var(--cafe-surface)', border: '2px solid var(--cafe-border-2)' }}
              >
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
                <div className="font-semibold mb-1" style={{ color: 'var(--cafe-gold)' }}>In-Depth Guided Tour</div>
                <div className="text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
                  Follow a structured demo with real customer, watch, shoe, mobile services, quote, and invoice records.
                </div>
              </button>
            </div>
          </div>
        </Modal>
      )}

      {activeTutorial && (
        <Modal title={activeTutorial.title} onClose={dismissTutorial}>
          <div className="space-y-3 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
            <p style={{ color: 'var(--cafe-text)' }}>{activeTutorial.intro}</p>
            <p className="font-semibold" style={{ color: 'var(--cafe-text)' }}>This page lets you:</p>
            <ul className="list-disc pl-5 space-y-1">
              {activeTutorial.features.map((item) => (
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

      {tourMode === 'guided' && showGuidedModal && currentGuidedStep && (
        <Modal title={currentGuidedStep.title} onClose={() => setShowGuidedModal(false)}>
          <div className="space-y-4 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
            <p style={{ color: 'var(--cafe-text)' }}>{currentGuidedStep.intro}</p>
            <div className="rounded-xl p-3" style={{ backgroundColor: 'var(--cafe-bg)', border: '1px solid var(--cafe-border)' }}>
              <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>
                Try this now
              </p>
              <p className="mt-1" style={{ color: 'var(--cafe-text)' }}>{currentGuidedStep.task}</p>
            </div>
            <div>
              <p className="font-semibold mb-2" style={{ color: 'var(--cafe-text)' }}>What to notice</p>
              <ul className="list-disc pl-5 space-y-1">
                {currentGuidedStep.highlights.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" className="flex-1" onClick={() => setShowGuidedModal(false)}>
                I will look around first
              </Button>
              {currentGuidedStep.actionPath ? (
                <Button
                  className="flex-1"
                  onClick={() => {
                    setShowGuidedModal(false)
                    navigate(currentGuidedStep.actionPath!)
                  }}
                >
                  {currentGuidedStep.actionLabel ?? 'Do it'}
                </Button>
              ) : (
                <Button
                  className="flex-1"
                  onClick={() => {
                    setShowGuidedModal(false)
                    exitGuidedTour()
                  }}
                >
                  Finish guided tour
                </Button>
              )}
            </div>
          </div>
        </Modal>
      )}

      {tourMode === 'guided' && !showWelcomeModal && currentGuidedStep && (
        <div
          className="fixed bottom-0 left-0 right-0 z-50"
          style={{
            backgroundColor: 'var(--cafe-espresso-2)',
            borderTop: '2px solid var(--cafe-gold)',
            boxShadow: '0 -4px 24px rgba(0,0,0,0.4)',
          }}
        >
          <div className="h-1" style={{ backgroundColor: 'var(--cafe-border)' }}>
            <div
              className="h-1 transition-all duration-300"
              style={{
                backgroundColor: 'var(--cafe-gold)',
                width: `${((guidedStep + 1) / guidedTourSteps.length) * 100}%`,
              }}
            />
          </div>
          <div className="px-4 py-3 sm:px-6">
            <div className="flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--cafe-gold)' }}>
                    Step {guidedStep + 1} of {guidedTourSteps.length}
                  </span>
                  <span className="text-xs font-medium" style={{ color: 'var(--cafe-text-mid)' }}>
                    - {currentGuidedStep.label}
                  </span>
                </div>
                <p className="text-sm line-clamp-2" style={{ color: 'var(--cafe-text-muted)' }}>
                  {currentGuidedStep.task}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => setShowGuidedModal(true)}
                  className="px-3 py-1.5 rounded-lg text-sm"
                  style={{ color: 'var(--cafe-text-muted)' }}
                >
                  Show tip
                </button>
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
                    Back
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
                  {guidedIsLast ? 'Finish Tour' : `Next: ${guidedNextLabel} ->`}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
