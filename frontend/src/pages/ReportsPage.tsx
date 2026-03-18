import { useMutation, useQuery } from '@tanstack/react-query'
import { BarChart3, DollarSign, Scale, Wallet, Download } from 'lucide-react'
import {
  getExportCustomersCsv,
  getExportInvoicesCsv,
  getExportJobsCsv,
  getExportMyData,
  getReportsSummary,
  getReportsTrends,
  getTenantActivity,
} from '@/lib/api'
import { Button, Card, PageHeader, Spinner } from '@/components/ui'
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

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function ReportsPage() {
  const { data, isLoading } = useQuery({ queryKey: ['reports-summary'], queryFn: () => getReportsSummary().then(r => r.data) })
  const { data: trends } = useQuery({ queryKey: ['reports-trends'], queryFn: () => getReportsTrends(6).then(r => r.data) })
  const { data: activity } = useQuery({ queryKey: ['reports-activity'], queryFn: () => getTenantActivity(50).then(r => r.data) })
  const exportJobsMut = useMutation({ mutationFn: () => getExportJobsCsv().then(r => { downloadBlob(r.data, 'jobs.csv'); return r }) })
  const exportCustomersMut = useMutation({ mutationFn: () => getExportCustomersCsv().then(r => { downloadBlob(r.data, 'customers.csv'); return r }) })
  const exportInvoicesMut = useMutation({ mutationFn: () => getExportInvoicesCsv().then(r => { downloadBlob(r.data, 'invoices.csv'); return r }) })
  const exportMyDataMut = useMutation({
    mutationFn: async () => {
      const { data: json } = await getExportMyData()
      const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' })
      downloadBlob(blob, 'my-data.json')
    },
  })

  if (isLoading) return <Spinner />
  if (!data) return <p style={{ color: 'var(--cafe-text-muted)' }}>No report data available.</p>

  const maxJobs = Math.max(...(trends?.months.map(m => m.jobs_opened) ?? [1]), 1)
  const maxRevenue = Math.max(...(trends?.months.map(m => m.revenue_cents) ?? [1]), 1)

  return (
    <div>
      <PageHeader
        title="Reports"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={() => exportJobsMut.mutate()} disabled={exportJobsMut.isPending}>
              <Download size={14} className="mr-1" /> Jobs CSV
            </Button>
            <Button variant="secondary" size="sm" onClick={() => exportCustomersMut.mutate()} disabled={exportCustomersMut.isPending}>
              <Download size={14} className="mr-1" /> Customers CSV
            </Button>
            <Button variant="secondary" size="sm" onClick={() => exportInvoicesMut.mutate()} disabled={exportInvoicesMut.isPending}>
              <Download size={14} className="mr-1" /> Invoices CSV
            </Button>
            <Button variant="ghost" size="sm" onClick={() => exportMyDataMut.mutate()} disabled={exportMyDataMut.isPending}>
              <Download size={14} className="mr-1" /> Export my data
            </Button>
          </div>
        }
      />

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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
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

      {trends && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <Card className="p-5">
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--cafe-text)' }}>Jobs Opened — Last 6 Months</h2>
            <div className="space-y-2">
              {trends.months.map(m => (
                <div key={m.month} className="flex items-center gap-3 text-xs">
                  <span className="w-16 shrink-0 font-medium" style={{ color: 'var(--cafe-text-muted)' }}>{m.month}</span>
                  <div className="flex-1 h-5 rounded overflow-hidden" style={{ backgroundColor: 'var(--cafe-bg)' }}>
                    <div
                      className="h-full rounded transition-all"
                      style={{
                        width: `${Math.round((m.jobs_opened / maxJobs) * 100)}%`,
                        backgroundColor: '#8D6725',
                        minWidth: m.jobs_opened > 0 ? 4 : 0,
                      }}
                    />
                  </div>
                  <span className="w-8 text-right font-semibold shrink-0" style={{ color: 'var(--cafe-text)' }}>{m.jobs_opened}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--cafe-text)' }}>Revenue — Last 6 Months</h2>
            <div className="space-y-2">
              {trends.months.map(m => (
                <div key={m.month} className="flex items-center gap-3 text-xs">
                  <span className="w-16 shrink-0 font-medium" style={{ color: 'var(--cafe-text-muted)' }}>{m.month}</span>
                  <div className="flex-1 h-5 rounded overflow-hidden" style={{ backgroundColor: 'var(--cafe-bg)' }}>
                    <div
                      className="h-full rounded transition-all"
                      style={{
                        width: `${Math.round((m.revenue_cents / maxRevenue) * 100)}%`,
                        backgroundColor: '#1F6D4C',
                        minWidth: m.revenue_cents > 0 ? 4 : 0,
                      }}
                    />
                  </div>
                  <span className="w-20 text-right font-semibold shrink-0" style={{ color: 'var(--cafe-text)' }}>{formatCents(m.revenue_cents)}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {activity && activity.length > 0 && (
        <Card className="p-5 mb-6">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Audit Log</h2>
          <div className="space-y-1 text-xs max-h-72 overflow-y-auto">
            {activity.map(ev => (
              <div key={ev.id} className="flex items-start gap-3 py-1.5 border-b" style={{ borderColor: 'var(--cafe-border)' }}>
                <span
                  className="px-1.5 py-0.5 rounded text-xs font-medium shrink-0 uppercase tracking-wide"
                  style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)' }}
                >
                  {ev.event_type.replace(/_/g, ' ')}
                </span>
                <span className="flex-1" style={{ color: 'var(--cafe-text-mid)' }}>{ev.event_summary}</span>
                <span className="shrink-0" style={{ color: 'var(--cafe-text-muted)' }}>
                  {new Date(ev.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
