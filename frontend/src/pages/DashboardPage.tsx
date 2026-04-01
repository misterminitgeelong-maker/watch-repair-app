import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Clock3,
  DollarSign,
  FileText,
  Receipt,
  UserCog,
  Users,
  Wrench,
} from 'lucide-react'
import {
  getBillingLimits,
  getReportsSummary,
  getReportsWidgets,
  listAutoKeyJobs,
  listCustomerAccounts,
  listCustomers,
  listInvoices,
  listJobs,
  listQuotes,
  listShoeRepairJobs,
  listUsers,
  type RepairJob,
} from '@/lib/api'
import { Badge, Card, PageHeader, Spinner } from '@/components/ui'
import { useAuth } from '@/context/AuthContext'
import { isChecklistDismissed, setChecklistDismissed } from '@/lib/onboarding'
import { formatCents, formatDate } from '@/lib/utils'
import { Link } from 'react-router-dom'

const CLOSED_JOB_STATUSES = ['no_go', 'completed', 'awaiting_collection', 'collected']
const GO_AHEAD_STATUSES = [
  'go_ahead',
  'parts_to_order',
  'sent_to_labanda',
  'quoted_by_labanda',
  'awaiting_parts',
  'working_on',
  'service',
  'completed',
  'awaiting_collection',
]

const DASHBOARD_CSS = `
@keyframes dashboardRise {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: translateY(0); }
}
.dashboard-rise { animation: dashboardRise 0.48s cubic-bezier(0.22, 1, 0.36, 1) both; }
.dashboard-panel {
  box-shadow: 0 2px 6px rgba(80,50,15,0.06), 0 10px 28px rgba(80,50,15,0.08);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.dashboard-panel:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(80,50,15,0.08), 0 20px 40px rgba(80,50,15,0.12);
}
`

type DashboardStatProps = {
  label: string
  value: string
  helper: string
  to: string
  icon: React.ElementType
  iconBg: string
  iconColor: string
  index: number
}

type RecentItem = {
  id: string
  title: string
  to: string
  created_at: string
  status: string
  typeLabel: string
  detail: string
}

function formatPlanName(planCode: string) {
  if (planCode === 'pro') return 'Pro'
  if (planCode === 'basic_watch') return 'Basic - Watch'
  if (planCode === 'basic_shoe') return 'Basic - Shoe'
  if (planCode === 'basic_auto_key') return 'Basic - Auto Key'
  if (planCode === 'basic_watch_shoe') return 'Basic +1 Tab (Watch + Shoe)'
  if (planCode === 'basic_watch_auto_key') return 'Basic +1 Tab (Watch + Auto Key)'
  if (planCode === 'basic_shoe_auto_key') return 'Basic +1 Tab (Shoe + Auto Key)'
  if (planCode === 'basic_all_tabs') return 'Basic +2 Tabs (All Service Tabs)'
  return planCode
}

function isOpenStatus(status: string) {
  return !CLOSED_JOB_STATUSES.includes(status)
}

function watchJobValue(job: RepairJob) {
  return job.cost_cents > 0 ? job.cost_cents : job.pre_quote_cents
}

function DashboardStatCard({ label, value, helper, to, icon: Icon, iconBg, iconColor, index }: DashboardStatProps) {
  return (
    <Link to={to} className="dashboard-rise block" style={{ animationDelay: `${index * 0.06}s` }}>
      <Card className="dashboard-panel h-full p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--cafe-text-muted)' }}>
              {label}
            </p>
            <p
              className="mt-2 text-3xl font-semibold leading-none"
              style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
            >
              {value}
            </p>
            <p className="mt-2 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
              {helper}
            </p>
          </div>
          <div className="flex h-11 w-11 items-center justify-center rounded-xl" style={{ backgroundColor: iconBg, color: iconColor }}>
            <Icon size={20} />
          </div>
        </div>
      </Card>
    </Link>
  )
}

export default function DashboardPage() {
  const { tenantId, role, planCode, availableSites, activeSiteTenantId, hasFeature } = useAuth()
  const [checklistDismissed, setChecklistDismissedState] = useState(false)
  const canViewAccountMetrics = role === 'owner' || role === 'platform_admin'

  const { data: jobs, isLoading: jobsLoading } = useQuery({ queryKey: ['jobs'], queryFn: () => listJobs().then((r) => r.data) })
  const { data: customers, isLoading: customersLoading } = useQuery({ queryKey: ['customers'], queryFn: () => listCustomers().then((r) => r.data) })
  const { data: quotes, isLoading: quotesLoading } = useQuery({ queryKey: ['quotes'], queryFn: () => listQuotes().then((r) => r.data) })
  const { data: invoices, isLoading: invoicesLoading } = useQuery({ queryKey: ['invoices'], queryFn: () => listInvoices().then((r) => r.data) })
  const { data: reports, isLoading: reportsLoading } = useQuery({ queryKey: ['reports-summary'], queryFn: () => getReportsSummary().then((r) => r.data) })
  const { data: shoeJobs } = useQuery({
    queryKey: ['shoe-repair-jobs', 'dashboard'],
    queryFn: () => listShoeRepairJobs().then((r) => r.data),
    enabled: hasFeature('shoe'),
  })
  const { data: autoKeyJobs } = useQuery({
    queryKey: ['auto-key-jobs', 'dashboard'],
    queryFn: () => listAutoKeyJobs().then((r) => r.data),
    enabled: hasFeature('auto_key'),
  })
  const { data: customerAccounts } = useQuery({
    queryKey: ['customer-accounts', 'dashboard'],
    queryFn: () => listCustomerAccounts().then((r) => r.data),
    enabled: hasFeature('customer_accounts'),
  })
  const { data: users } = useQuery({
    queryKey: ['users', 'dashboard'],
    queryFn: () => listUsers().then((r) => r.data),
    enabled: canViewAccountMetrics,
  })
  const { data: billing } = useQuery({
    queryKey: ['billing-limits', 'dashboard'],
    queryFn: () => getBillingLimits().then((r) => r.data),
    enabled: canViewAccountMetrics,
  })
  const { data: widgets } = useQuery({
    queryKey: ['reports-widgets'],
    queryFn: () => getReportsWidgets().then((r) => r.data),
  })

  useEffect(() => {
    setChecklistDismissedState(isChecklistDismissed(tenantId))
  }, [tenantId])

  const watchOpenJobs = useMemo(() => (jobs ?? []).filter((job) => isOpenStatus(job.status)), [jobs])
  const watchAwaitingGoAhead = useMemo(() => (jobs ?? []).filter((job) => job.status === 'awaiting_go_ahead'), [jobs])
  const watchOutstandingValue = useMemo(
    () => (jobs ?? [])
      .filter((job) => GO_AHEAD_STATUSES.includes(job.status))
      .reduce((sum, job) => sum + watchJobValue(job), 0),
    [jobs],
  )
  const shoeOpenJobs = useMemo(() => (shoeJobs ?? []).filter((job) => isOpenStatus(job.status)), [shoeJobs])
  const autoOpenJobs = useMemo(() => (autoKeyJobs ?? []).filter((job) => isOpenStatus(job.status)), [autoKeyJobs])
  const quotesPending = useMemo(() => (quotes ?? []).filter((quote) => quote.status === 'draft' || quote.status === 'sent'), [quotes])
  const invoicesOpen = useMemo(() => (invoices ?? []).filter((invoice) => invoice.status !== 'paid'), [invoices])
  const invoicesOpenValue = useMemo(() => invoicesOpen.reduce((sum, invoice) => sum + invoice.total_cents, 0), [invoicesOpen])
  const totalServiceJobs = watchOpenJobs.length + shoeOpenJobs.length + autoOpenJobs.length
  const urgentAcrossServiceLines = [...(jobs ?? []), ...(shoeJobs ?? []), ...(autoKeyJobs ?? [])].filter(
    (job) => job.priority === 'high' || job.priority === 'urgent',
  ).length

  const checklist = [
    { key: 'customer', label: 'Add your first customer', done: (customers?.length ?? 0) > 0, to: '/customers' },
    { key: 'watch', label: 'Create a watch repair', done: (jobs?.length ?? 0) > 0, to: '/jobs' },
    { key: 'quote', label: 'Send a quote', done: (quotes?.length ?? 0) > 0, to: '/quotes' },
    { key: 'invoice', label: 'Raise an invoice', done: (invoices?.length ?? 0) > 0, to: '/invoices' },
    { key: 'team', label: 'Set up team accounts', done: (users?.length ?? 0) > 1, to: '/accounts' },
  ]
  const checklistDone = checklist.filter((item) => item.done).length

  const recentItems = useMemo<RecentItem[]>(() => {
    const watchItems = (jobs ?? []).map((job) => ({
      id: job.id,
      title: job.title,
      to: `/jobs/${job.id}`,
      created_at: job.created_at,
      status: job.status,
      typeLabel: 'Watch repair',
      detail: `#${job.job_number}`,
    }))
    const shoeItems = (shoeJobs ?? []).map((job) => ({
      id: job.id,
      title: job.title,
      to: `/shoe-repairs/${job.id}`,
      created_at: job.created_at,
      status: job.status,
      typeLabel: 'Shoe repair',
      detail: `#${job.job_number}`,
    }))
    const autoItems = (autoKeyJobs ?? []).map((job) => ({
      id: job.id,
      title: job.title,
      to: `/auto-key/${job.id}`,
      created_at: job.created_at,
      status: job.status,
      typeLabel: 'Auto key',
      detail: `#${job.job_number}`,
    }))

    return [...watchItems, ...shoeItems, ...autoItems]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 8)
  }, [autoKeyJobs, jobs, shoeJobs])

  if (jobsLoading || customersLoading || quotesLoading || invoicesLoading || reportsLoading) {
    return <Spinner />
  }

  const actionCount = (widgets?.overdue_jobs_count ?? 0) + (widgets?.quotes_pending_7d_count ?? 0) + (widgets?.overdue_invoices_count ?? 0)

  const statCards = [
    {
      label: 'All Active Jobs',
      value: String(totalServiceJobs),
      helper: `${urgentAcrossServiceLines} high-priority across all service lines`,
      to: '/jobs',
      icon: Wrench,
      iconBg: '#EFE7DC',
      iconColor: '#8D6725',
    },
    {
      label: 'Customers',
      value: String(customers?.length ?? 0),
      helper: `${customerAccounts?.length ?? 0} business account groups`,
      to: '/customers',
      icon: Users,
      iconBg: '#DFF0EC',
      iconColor: '#2A6B65',
    },
    {
      label: 'Quotes Awaiting Action',
      value: String(quotesPending.length),
      helper: `${reports?.sales_funnel.approval_rate_percent ?? 0}% approval rate`,
      to: '/quotes',
      icon: FileText,
      iconBg: '#F3EBF9',
      iconColor: '#68409C',
    },
    {
      label: 'Open Invoices',
      value: String(invoicesOpen.length),
      helper: `${formatCents(invoicesOpenValue)} awaiting payment`,
      to: '/invoices',
      icon: Receipt,
      iconBg: '#FDE9E1',
      iconColor: '#A2502E',
    },
    {
      label: 'Outstanding Work Value',
      value: formatCents((reports?.financials.outstanding_cents ?? 0) || watchOutstandingValue),
      helper: `${watchAwaitingGoAhead.length} watch jobs waiting for approval`,
      to: '/reports',
      icon: DollarSign,
      iconBg: '#E8F0E4',
      iconColor: '#3B6B42',
    },
    {
      label: 'Team & Sites',
      value: `${users?.length ?? 1} / ${availableSites.length}`,
      helper: `${formatPlanName(planCode)} plan${availableSites.length > 1 ? ' with multi-site context' : ''}`,
      to: '/accounts',
      icon: UserCog,
      iconBg: '#E6EDF8',
      iconColor: '#345B9C',
    },
  ]

  return (
    <div style={{ position: 'relative' }}>
      <style>{DASHBOARD_CSS}</style>

      <div
        style={{
          position: 'absolute',
          top: 70,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 1100,
          height: 300,
          pointerEvents: 'none',
          background: 'radial-gradient(ellipse 780px 220px at 50% 50%, rgba(201,162,72,0.10) 0%, transparent 72%)',
          zIndex: 0,
        }}
      />

      <div style={{ position: 'relative', zIndex: 1 }}>
        <PageHeader title="Operations Dashboard" />

        <Card className="dashboard-panel mb-6 overflow-hidden">
          <div className="grid gap-0 lg:grid-cols-[1.4fr_0.9fr]">
            <div className="p-6 sm:p-7" style={{ background: 'linear-gradient(135deg, rgba(61,35,18,0.98) 0%, rgba(92,63,37,0.96) 100%)' }}>
              <p className="text-xs font-semibold uppercase tracking-[0.24em]" style={{ color: '#D6C4AD' }}>
                Shop-wide overview
              </p>
              <h2 className="mt-3 text-3xl font-semibold leading-tight" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: '#FFF7EA' }}>
                All your repairs, one place.
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7" style={{ color: '#E7D8C3' }}>
                {totalServiceJobs > 0
                  ? `${totalServiceJobs} active ${totalServiceJobs === 1 ? 'job' : 'jobs'} across your service lines.`
                  : 'No active jobs right now — ready for the next one.'}
              </p>
              <div className="mt-5 flex flex-wrap gap-2 text-xs font-medium">
                <span className="rounded-full px-3 py-1.5" style={{ backgroundColor: 'rgba(255,255,255,0.08)', color: '#FFF7EA' }}>
                  {formatPlanName(planCode)} plan
                </span>
                <span className="rounded-full px-3 py-1.5" style={{ backgroundColor: 'rgba(255,255,255,0.08)', color: '#FFF7EA' }}>
                  {availableSites.length} {availableSites.length === 1 ? 'site' : 'sites'} linked
                </span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-px" style={{ backgroundColor: 'rgba(255,255,255,0.08)' }}>
              <div className="p-5" style={{ backgroundColor: '#F7F0E6' }}>
                <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Revenue</p>
                <p className="mt-2 text-2xl font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
                  {formatCents(reports?.financials.revenue_cents ?? 0)}
                </p>
              </div>
              <div className="p-5" style={{ backgroundColor: '#F4ECE2' }}>
                <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Gross Profit</p>
                <p className="mt-2 text-2xl font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
                  {formatCents(reports?.financials.gross_profit_cents ?? 0)}
                </p>
              </div>
              <div className="p-5" style={{ backgroundColor: '#F4ECE2' }}>
                <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Approval Rate</p>
                <p className="mt-2 text-2xl font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
                  {reports?.sales_funnel.approval_rate_percent ?? 0}%
                </p>
              </div>
              <div className="p-5" style={{ backgroundColor: '#F7F0E6' }}>
                <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Avg / Job</p>
                <p className="mt-2 text-2xl font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
                  {formatCents(reports?.operations.avg_revenue_per_job_cents ?? 0)}
                </p>
              </div>
            </div>
          </div>
        </Card>

        {!checklistDismissed && (
          <Card className="mb-6 p-4 sm:p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>Launch checklist</p>
                <p className="mt-1 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                  Progress {checklistDone}/{checklist.length} completed
                </p>
              </div>
              <button
                type="button"
                className="text-xs font-semibold"
                style={{ color: 'var(--cafe-amber)' }}
                onClick={() => {
                  setChecklistDismissed(tenantId, true)
                  setChecklistDismissedState(true)
                }}
              >
                Dismiss
              </button>
            </div>

            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-5">
              {checklist.map((item) => (
                <Link
                  key={item.key}
                  to={item.to}
                  className="rounded-xl border px-3 py-3 text-sm"
                  style={{
                    borderColor: 'var(--cafe-border)',
                    backgroundColor: item.done ? '#EAF4EA' : 'var(--cafe-bg)',
                    color: 'var(--cafe-text)',
                  }}
                >
                  <span className="font-semibold">{item.done ? 'Done' : 'Next'}</span> · {item.label}
                </Link>
              ))}
            </div>
          </Card>
        )}

        {actionCount > 0 && (
          <Card className="mb-6 p-4 flex flex-wrap items-center gap-4" style={{ backgroundColor: '#FFFBEB', borderColor: '#FCD34D' }}>
            <span className="font-semibold" style={{ color: '#92400E' }}>Action needed</span>
            {widgets && (
              <div className="flex flex-wrap gap-4 text-sm">
                {(widgets.overdue_jobs_count ?? 0) > 0 && (
                  <Link to="/jobs?status=awaiting_go_ahead" className="underline" style={{ color: '#B45309' }}>
                    {widgets.overdue_jobs_count} job(s) awaiting go-ahead 14+ days
                  </Link>
                )}
                {(widgets.quotes_pending_7d_count ?? 0) > 0 && (
                  <Link to="/quotes" className="underline" style={{ color: '#B45309' }}>
                    {widgets.quotes_pending_7d_count} quote(s) sent 7+ days, no response
                  </Link>
                )}
                {(widgets.overdue_invoices_count ?? 0) > 0 && (
                  <Link to="/invoices" className="underline" style={{ color: '#B45309' }}>
                    {widgets.overdue_invoices_count} unpaid invoice(s)
                  </Link>
                )}
              </div>
            )}
          </Card>
        )}

        <div className="mb-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {statCards.map((card, index) => (
            <DashboardStatCard key={card.label} {...card} index={index} />
          ))}
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.3fr_0.9fr]">
          <Card className="dashboard-panel overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              <div>
                <h2 className="text-lg font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
                  Live Service Queue
                </h2>
                <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
                  The newest repair activity across watch, shoe, and auto-key work.
                </p>
              </div>
              <Link to="/jobs" className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-amber)' }}>
                Open workflow
              </Link>
            </div>

            <div>
              {recentItems.map((item, index) => (
                <Link
                  key={`${item.typeLabel}-${item.id}`}
                  to={item.to}
                  className="flex items-center justify-between gap-3 px-5 py-3.5 transition-colors"
                  style={{ borderBottom: index < recentItems.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#F5EDE0' }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>
                        {item.typeLabel}
                      </span>
                      <span className="text-[11px]" style={{ color: 'var(--cafe-text-muted)' }}>
                        {item.detail}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{item.title}</p>
                    <p className="mt-1 text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(item.created_at)}</p>
                  </div>
                  <Badge status={item.status} />
                </Link>
              ))}

              {recentItems.length === 0 && (
                <p className="px-5 py-8 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>
                  No recent jobs yet.
                </p>
              )}
            </div>
          </Card>

          <div className="space-y-6">
            <Card className="dashboard-panel p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ backgroundColor: '#E8F0E4', color: '#3B6B42' }}>
                  <DollarSign size={18} />
                </div>
                <div>
                  <h2 className="text-lg font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
                    Commercial Pulse
                  </h2>
                  <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
                    What the shop has billed, recovered, and still needs to chase.
                  </p>
                </div>
              </div>

              <div className="mt-4 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span style={{ color: 'var(--cafe-text-mid)' }}>Billed total</span>
                  <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(reports?.financials.billed_cents ?? 0)}</strong>
                </div>
                <div className="flex items-center justify-between">
                  <span style={{ color: 'var(--cafe-text-mid)' }}>Revenue received</span>
                  <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(reports?.financials.revenue_cents ?? 0)}</strong>
                </div>
                <div className="flex items-center justify-between">
                  <span style={{ color: 'var(--cafe-text-mid)' }}>Outstanding</span>
                  <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(reports?.financials.outstanding_cents ?? 0)}</strong>
                </div>
                <div className="flex items-center justify-between">
                  <span style={{ color: 'var(--cafe-text-mid)' }}>Gross margin</span>
                  <strong style={{ color: 'var(--cafe-text)' }}>{reports?.financials.gross_margin_percent ?? 0}%</strong>
                </div>
              </div>
            </Card>

            <Card className="dashboard-panel p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg" style={{ backgroundColor: '#E6EDF8', color: '#345B9C' }}>
                  <Clock3 size={18} />
                </div>
                <div>
                  <h2 className="text-lg font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}>
                    Operational Pressure
                  </h2>
                  <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
                    Where workflow congestion is starting to show.
                  </p>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-xl border p-3" style={{ borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
                  <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Watch OK wait</p>
                  <p className="mt-1 text-xl font-semibold" style={{ color: 'var(--cafe-text)' }}>{watchAwaitingGoAhead.length}</p>
                </div>
                <div className="rounded-xl border p-3" style={{ borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
                  <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Quotes pending</p>
                  <p className="mt-1 text-xl font-semibold" style={{ color: 'var(--cafe-text)' }}>{quotesPending.length}</p>
                </div>
                <div className="rounded-xl border p-3" style={{ borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
                  <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Urgent jobs</p>
                  <p className="mt-1 text-xl font-semibold" style={{ color: 'var(--cafe-text)' }}>{urgentAcrossServiceLines}</p>
                </div>
                <div className="rounded-xl border p-3" style={{ borderColor: 'var(--cafe-border)', backgroundColor: 'var(--cafe-bg)' }}>
                  <p className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>Open invoices</p>
                  <p className="mt-1 text-xl font-semibold" style={{ color: 'var(--cafe-text)' }}>{invoicesOpen.length}</p>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}