import { useQuery } from '@tanstack/react-query'
import { BarChart3, DollarSign, Scale, Wallet } from 'lucide-react'
import { getReportsSummary } from '@/lib/api'
import { Card, PageHeader, Spinner } from '@/components/ui'
import { formatCents } from '@/lib/utils'

function MetricCard({
  label,
  value,
  icon: Icon,
  iconBg,
  iconColor,
}: {
  label: string
  value: string
  icon: React.ElementType
  iconBg: string
  iconColor: string
}) {
  return (
    <Card className="p-5 flex items-center gap-4">
      <div className="w-11 h-11 rounded-lg flex items-center justify-center" style={{ backgroundColor: iconBg }}>
        <Icon size={20} style={{ color: iconColor }} />
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide font-medium" style={{ color: 'var(--cafe-text-muted)' }}>{label}</p>
        <p className="text-2xl font-semibold" style={{ color: 'var(--cafe-text)', fontFamily: "'Playfair Display', Georgia, serif" }}>{value}</p>
      </div>
    </Card>
  )
}

export default function ReportsPage() {
  const { data, isLoading } = useQuery({ queryKey: ['reports-summary'], queryFn: () => getReportsSummary().then(r => r.data) })

  if (isLoading) return <Spinner />
  if (!data) return <p style={{ color: 'var(--cafe-text-muted)' }}>No report data available.</p>

  return (
    <div>
      <PageHeader title="Reports" />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <MetricCard
          label="Revenue"
          value={formatCents(data.financials.revenue_cents)}
          icon={DollarSign}
          iconBg="#E8F6EE"
          iconColor="#1F6D4C"
        />
        <MetricCard
          label="Cost"
          value={formatCents(data.financials.cost_cents)}
          icon={Wallet}
          iconBg="#FDEBD4"
          iconColor="#9B4E0F"
        />
        <MetricCard
          label="Gross Profit"
          value={formatCents(data.financials.gross_profit_cents)}
          icon={Scale}
          iconBg="#F3E9FF"
          iconColor="#5B3F92"
        />
        <MetricCard
          label="Outstanding"
          value={formatCents(data.financials.outstanding_cents)}
          icon={BarChart3}
          iconBg="#FCE8E8"
          iconColor="#8B3A3A"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Business KPIs</h2>
          <div className="space-y-2 text-sm">
            <p style={{ color: 'var(--cafe-text-mid)' }}>Jobs: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.jobs}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Customers: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.customers}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Watches: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.watches}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Quotes: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.quotes}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Invoices: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.invoices}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Approval rate: <strong style={{ color: 'var(--cafe-text)' }}>{data.sales_funnel.approval_rate_percent}%</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Gross margin: <strong style={{ color: 'var(--cafe-text)' }}>{data.financials.gross_margin_percent}%</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Avg revenue per job: <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(data.operations.avg_revenue_per_job_cents)}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Tracked work minutes: <strong style={{ color: 'var(--cafe-text)' }}>{data.operations.work_minutes}</strong></p>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Financial Breakdown</h2>
          <div className="space-y-2 text-sm">
            <p style={{ color: 'var(--cafe-text-mid)' }}>Billed total: <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(data.financials.billed_cents)}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Revenue received: <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(data.financials.revenue_cents)}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Internal cost tracked: <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(data.financials.cost_cents)}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Gross profit: <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(data.financials.gross_profit_cents)}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Outstanding: <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(data.financials.outstanding_cents)}</strong></p>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Job Status Distribution</h2>
          <div className="space-y-2 text-sm">
            {Object.entries(data.jobs_by_status).map(([status, count]) => (
              <p key={status} style={{ color: 'var(--cafe-text-mid)' }}>
                {status.replace(/_/g, ' ')}: <strong style={{ color: 'var(--cafe-text)' }}>{count}</strong>
              </p>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Quote Status Distribution</h2>
          <div className="space-y-2 text-sm">
            {Object.entries(data.quotes_by_status).map(([status, count]) => (
              <p key={status} style={{ color: 'var(--cafe-text-mid)' }}>
                {status.replace(/_/g, ' ')}: <strong style={{ color: 'var(--cafe-text)' }}>{count}</strong>
              </p>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
