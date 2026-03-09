import { useQuery } from '@tanstack/react-query'
import { Wrench, Users, FileText, Receipt, Clock } from 'lucide-react'
import { listJobs, listCustomers, listQuotes, listInvoices } from '@/lib/api'
import { Card, PageHeader, Badge, Spinner } from '@/components/ui'
import { formatCents, formatDate } from '@/lib/utils'
import { Link } from 'react-router-dom'

const STAT_STYLES = [
  { iconBg: '#F5E8CC', iconColor: '#9B7228', label: 'Open Jobs' },
  { iconBg: '#DFF0EC', iconColor: '#2A6B65', label: 'Customers' },
  { iconBg: '#FDECD3', iconColor: '#9B4E0F', label: 'Pending Quotes' },
  { iconBg: '#F5E8E8', iconColor: '#8B3A3A', label: 'Outstanding' },
]

function StatCard({
  label, value, icon: Icon, iconBg, iconColor,
}: {
  label: string; value: number; icon: React.ElementType; iconBg: string; iconColor: string
}) {
  return (
    <Card className="p-6 flex items-center gap-5">
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
        style={{ backgroundColor: iconBg }}
      >
        <Icon size={22} style={{ color: iconColor }} />
      </div>
      <div>
        <p
          className="text-3xl font-semibold leading-none"
          style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
        >
          {value}
        </p>
        <p className="text-xs mt-1.5 tracking-wide uppercase font-medium" style={{ color: 'var(--cafe-text-muted)' }}>
          {label}
        </p>
      </div>
    </Card>
  )
}

export default function DashboardPage() {
  const { data: jobs, isLoading: jobsLoading } = useQuery({ queryKey: ['jobs'], queryFn: () => listJobs().then(r => r.data) })
  const { data: customers } = useQuery({ queryKey: ['customers'], queryFn: () => listCustomers().then(r => r.data) })
  const { data: quotes } = useQuery({ queryKey: ['quotes'], queryFn: () => listQuotes().then(r => r.data) })
  const { data: invoices } = useQuery({ queryKey: ['invoices'], queryFn: () => listInvoices().then(r => r.data) })

  const openJobs = jobs?.filter(j => !['collected', 'no_go'].includes(j.status)) ?? []
  const pendingQuotes = quotes?.filter(q => q.status === 'sent') ?? []
  const unpaidInvoices = invoices?.filter(i => i.status === 'unpaid') ?? []
  const unpaidTotal = unpaidInvoices.reduce((s, i) => s + i.total_cents, 0)

  if (jobsLoading) return <Spinner />

  return (
    <div>
      <PageHeader title="Overview" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label={STAT_STYLES[0].label} value={openJobs.length}          icon={Wrench}  iconBg={STAT_STYLES[0].iconBg} iconColor={STAT_STYLES[0].iconColor} />
        <StatCard label={STAT_STYLES[1].label} value={customers?.length ?? 0}  icon={Users}   iconBg={STAT_STYLES[1].iconBg} iconColor={STAT_STYLES[1].iconColor} />
        <StatCard label={STAT_STYLES[2].label} value={pendingQuotes.length}     icon={FileText} iconBg={STAT_STYLES[2].iconBg} iconColor={STAT_STYLES[2].iconColor} />
        <StatCard label={STAT_STYLES[3].label} value={unpaidInvoices.length}   icon={Receipt}  iconBg={STAT_STYLES[3].iconBg} iconColor={STAT_STYLES[3].iconColor} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Jobs */}
        <Card>
          <div
            className="flex items-center justify-between px-5 py-4"
            style={{ borderBottom: '1px solid var(--cafe-border)' }}
          >
            <h2
              className="font-semibold flex items-center gap-2"
              style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
            >
              <Clock size={16} style={{ color: 'var(--cafe-gold-dark)' }} />
              Active Jobs
            </h2>
            <Link
              to="/jobs"
              className="text-xs font-medium tracking-wide uppercase transition-colors"
              style={{ color: 'var(--cafe-amber)' }}
            >
              View all
            </Link>
          </div>
          <div>
            {openJobs.slice(0, 6).map((job, i) => (
              <Link
                key={job.id}
                to={`/jobs/${job.id}`}
                className="flex items-center justify-between px-5 py-3.5 transition-colors"
                style={{
                  borderBottom: i < Math.min(openJobs.length, 6) - 1 ? '1px solid var(--cafe-border)' : 'none',
                }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>{job.title}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>#{job.job_number} · {formatDate(job.created_at)}</p>
                </div>
                <Badge status={job.status} />
              </Link>
            ))}
            {openJobs.length === 0 && (
              <p className="px-5 py-8 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>
                No active jobs
              </p>
            )}
          </div>
        </Card>

        {/* Outstanding Invoices */}
        <Card>
          <div
            className="flex items-center justify-between px-5 py-4"
            style={{ borderBottom: '1px solid var(--cafe-border)' }}
          >
            <h2
              className="font-semibold flex items-center gap-2"
              style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
            >
              <Receipt size={16} style={{ color: 'var(--cafe-gold-dark)' }} />
              Outstanding Invoices
            </h2>
            <Link
              to="/invoices"
              className="text-xs font-medium tracking-wide uppercase transition-colors"
              style={{ color: 'var(--cafe-amber)' }}
            >
              View all
            </Link>
          </div>
          <div>
            {unpaidInvoices.slice(0, 6).map((inv, i) => (
              <Link
                key={inv.id}
                to={`/invoices/${inv.id}`}
                className="flex items-center justify-between px-5 py-3.5 transition-colors"
                style={{
                  borderBottom: i < Math.min(unpaidInvoices.length, 6) - 1 ? '1px solid var(--cafe-border)' : 'none',
                }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--cafe-text)' }}>#{inv.invoice_number}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--cafe-text-muted)' }}>{formatDate(inv.created_at)}</p>
                </div>
                <span className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>{formatCents(inv.total_cents)}</span>
              </Link>
            ))}
            {unpaidInvoices.length === 0 && (
              <p className="px-5 py-8 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>
                No outstanding invoices
              </p>
            )}
          </div>
          {unpaidTotal > 0 && (
            <div
              className="px-5 py-3 flex justify-between items-center"
              style={{ borderTop: '1px solid var(--cafe-border)' }}
            >
              <span className="text-xs font-medium tracking-wide uppercase" style={{ color: 'var(--cafe-text-muted)' }}>Total outstanding</span>
              <span className="text-sm font-bold" style={{ color: 'var(--cafe-text)' }}>{formatCents(unpaidTotal)}</span>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
