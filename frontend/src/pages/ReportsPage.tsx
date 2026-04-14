import { useMutation, useQuery } from '@tanstack/react-query'
import { BarChart3, DollarSign, Scale, Wallet, ChevronDown } from 'lucide-react'
import { useRef, useState } from 'react'
import {
  getExportCustomersCsv,
  getExportInvoicesCsv,
  getExportJobsCsv,
  getExportMyData,
  getReportsSummary,
  getReportsTrends,
  getReportsTechBreakdown,
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
  const { data: techBreakdown } = useQuery({ queryKey: ['reports-tech-breakdown'], queryFn: () => getReportsTechBreakdown().then(r => r.data) })
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

  const [exportOpen, setExportOpen] = useState(false)
  const exportRef = useRef<HTMLDivElement>(null)

  const anyExporting = exportJobsMut.isPending || exportCustomersMut.isPending || exportInvoicesMut.isPending || exportMyDataMut.isPending

  if (isLoading) return <div><PageHeader title="Reports" /><Spinner /></div>
  if (!data) return <div><PageHeader title="Reports" /><p className="mt-4" style={{ color: 'var(--cafe-text-muted)' }}>No report data available.</p></div>

  const maxJobs = Math.max(...(trends?.months.map(m => m.jobs_opened) ?? [1]), 1)
  const maxRevenue = Math.max(...(trends?.months.map(m => m.revenue_cents) ?? [1]), 1)

  return (
    <div>
      <PageHeader
        title="Reports"
        action={
          <div className="relative" ref={exportRef}>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setExportOpen(o => !o)}
              disabled={anyExporting}
            >
              Export <ChevronDown size={14} className="ml-1" />
            </Button>
            {exportOpen && (
              <div
                className="absolute right-0 mt-1 w-44 rounded-lg shadow-lg z-20 py-1"
                style={{ backgroundColor: 'var(--cafe-card)', border: '1px solid var(--cafe-border)' }}
                onBlur={() => setExportOpen(false)}
              >
                {[
                  { label: 'Jobs CSV', action: () => exportJobsMut.mutate() },
                  { label: 'Customers CSV', action: () => exportCustomersMut.mutate() },
                  { label: 'Invoices CSV', action: () => exportInvoicesMut.mutate() },
                  { label: 'My data (JSON)', action: () => exportMyDataMut.mutate() },
                ].map(item => (
                  <button
                    key={item.label}
                    className="w-full text-left px-4 py-2 text-sm hover:opacity-70 transition-opacity"
                    style={{ color: 'var(--cafe-text)' }}
                    onClick={() => { item.action(); setExportOpen(false) }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            )}
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

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Business KPIs</h2>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <p style={{ color: 'var(--cafe-text-mid)' }}>Jobs: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.jobs}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Customers: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.customers}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Watches: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.watches}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Quotes: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.quotes}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Invoices: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.invoices}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Billed: <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(data.financials.billed_cents)}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Approval rate: <strong style={{ color: 'var(--cafe-text)' }}>{data.sales_funnel.approval_rate_percent}%</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Gross margin: <strong style={{ color: 'var(--cafe-text)' }}>{data.financials.gross_margin_percent}%</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Avg / job: <strong style={{ color: 'var(--cafe-text)' }}>{formatCents(data.operations.avg_revenue_per_job_cents)}</strong></p>
            <p style={{ color: 'var(--cafe-text-mid)' }}>Work mins: <strong style={{ color: 'var(--cafe-text)' }}>{data.operations.work_minutes}</strong></p>
            {data.operations.avg_turnaround_days != null && (
              <p style={{ color: 'var(--cafe-text-mid)' }}>Avg turnaround: <strong style={{ color: 'var(--cafe-text)' }}>{data.operations.avg_turnaround_days}d</strong></p>
            )}
            <p style={{ color: 'var(--cafe-text-mid)' }}>Quote→invoice: <strong style={{ color: 'var(--cafe-text)' }}>{data.operations.quote_to_invoice_pct}%</strong></p>
            {data.operations.avg_quote_response_hours != null && (
              <p style={{ color: 'var(--cafe-text-mid)' }}>Quote response: <strong style={{ color: 'var(--cafe-text)' }}>{data.operations.avg_quote_response_hours}h avg</strong></p>
            )}
          </div>
        </Card>

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
          {Object.keys(data.quotes_by_status).length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>No quotes sent yet.</p>
          ) : (
            <div className="space-y-2 text-sm">
              {Object.entries(data.quotes_by_status).map(([status, count]) => (
                <p key={status} style={{ color: 'var(--cafe-text-mid)' }}>
                  {status.replace(/_/g, ' ')}: <strong style={{ color: 'var(--cafe-text)' }}>{count}</strong>
                </p>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Shoe repair section */}
      {(data.counts.shoe_jobs ?? 0) > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
          <Card className="p-5">
            <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Shoe Jobs</h2>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <p style={{ color: 'var(--cafe-text-mid)' }}>Total: <strong style={{ color: 'var(--cafe-text)' }}>{data.counts.shoe_jobs}</strong></p>
              {data.shoe_quotes && (
                <>
                  <p style={{ color: 'var(--cafe-text-mid)' }}>Quote approval: <strong style={{ color: 'var(--cafe-text)' }}>{data.shoe_quotes.approval_rate_percent}%</strong></p>
                  <p style={{ color: 'var(--cafe-text-mid)' }}>Quotes sent: <strong style={{ color: 'var(--cafe-text)' }}>{(data.shoe_quotes.by_status.sent ?? 0) + (data.shoe_quotes.by_status.approved ?? 0) + (data.shoe_quotes.by_status.declined ?? 0)}</strong></p>
                </>
              )}
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Shoe Job Status Distribution</h2>
            {Object.keys(data.shoe_jobs_by_status ?? {}).length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>No shoe jobs yet.</p>
            ) : (
              <div className="space-y-2 text-sm">
                {Object.entries(data.shoe_jobs_by_status ?? {}).map(([status, count]) => (
                  <p key={status} style={{ color: 'var(--cafe-text-mid)' }}>
                    {status.replace(/_/g, ' ')}: <strong style={{ color: 'var(--cafe-text)' }}>{count as number}</strong>
                  </p>
                ))}
              </div>
            )}
          </Card>

          <Card className="p-5">
            <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Shoe Quote Status</h2>
            {Object.keys(data.shoe_quotes?.by_status ?? {}).length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>No shoe quotes sent yet.</p>
            ) : (
              <div className="space-y-2 text-sm">
                {Object.entries(data.shoe_quotes?.by_status ?? {}).map(([status, count]) => (
                  <p key={status} style={{ color: 'var(--cafe-text-mid)' }}>
                    {status.replace(/_/g, ' ')}: <strong style={{ color: 'var(--cafe-text)' }}>{count as number}</strong>
                  </p>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

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

      {techBreakdown && techBreakdown.length > 0 && (
        <Card className="p-5 mb-6">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--cafe-text)' }}>Technician Breakdown</h2>
          <div className="space-y-2">
            {techBreakdown.map(t => (
              <div key={t.user_id} className="flex items-center justify-between text-sm">
                <span style={{ color: 'var(--cafe-text-mid)' }}>{t.user_name}</span>
                <span className="flex gap-4">
                  <span style={{ color: 'var(--cafe-text-muted)' }}>{t.jobs_count} job{t.jobs_count !== 1 ? 's' : ''}</span>
                  <strong style={{ color: 'var(--cafe-text)' }}>{Math.floor(t.total_minutes / 60)}h {t.total_minutes % 60}m</strong>
                </span>
              </div>
            ))}
          </div>
        </Card>
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
