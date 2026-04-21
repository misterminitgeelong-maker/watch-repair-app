import { useMutation, useQuery } from '@tanstack/react-query'
import { BarChart3, DollarSign, Scale, Wallet, ChevronDown, TrendingUp, Users, Clock } from 'lucide-react'
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

type PeriodKey = '3m' | '6m' | '12m'
const PERIODS: { key: PeriodKey; label: string; months: number }[] = [
  { key: '3m', label: '3 months', months: 3 },
  { key: '6m', label: '6 months', months: 6 },
  { key: '12m', label: '12 months', months: 12 },
]

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
        <p className="text-xs uppercase tracking-wide font-medium" style={{ color: 'var(--ms-text-muted)' }}>{label}</p>
        <p className="text-2xl font-semibold" style={{ color: 'var(--ms-text)' }}>{value}</p>
      </div>
    </Card>
  )
}

interface BarDatum {
  label: string
  value: number
  display: string
}
function VerticalBarChart({ data, color, height = 140 }: { data: BarDatum[]; color: string; height?: number }) {
  const max = Math.max(...data.map(d => d.value), 1)
  return (
    <div className="flex items-end gap-2" style={{ height: height + 32 }}>
      {data.map(d => {
        const h = Math.round((d.value / max) * height)
        return (
          <div key={d.label} className="flex-1 flex flex-col items-center gap-1 min-w-0">
            <span className="text-[10px] font-semibold" style={{ color: 'var(--ms-text)' }}>{d.display}</span>
            <div
              className="w-full rounded-t transition-all"
              style={{
                height: Math.max(h, d.value > 0 ? 3 : 0),
                backgroundColor: color,
                minHeight: d.value > 0 ? 3 : 0,
              }}
              title={`${d.label}: ${d.display}`}
            />
            <span className="text-[10px] truncate w-full text-center" style={{ color: 'var(--ms-text-muted)' }}>{d.label}</span>
          </div>
        )
      })}
    </div>
  )
}

function SalesFunnel({
  received, quoted, approved, completed, collected,
}: { received: number; quoted: number; approved: number; completed: number; collected: number }) {
  const stages = [
    { label: 'Received', value: received, color: 'var(--ms-accent)' },
    { label: 'Quoted', value: quoted, color: '#2A5FA0' },
    { label: 'Approved', value: approved, color: '#6840B4' },
    { label: 'Completed', value: completed, color: '#1A6A3A' },
    { label: 'Collected', value: collected, color: '#5A4A3B' },
  ]
  const max = Math.max(received, 1)
  return (
    <div className="space-y-2">
      {stages.map((s, i) => {
        const pct = Math.round((s.value / max) * 100)
        const conversion = i > 0 && stages[i - 1].value > 0 ? Math.round((s.value / stages[i - 1].value) * 100) : null
        return (
          <div key={s.label}>
            <div className="flex justify-between items-baseline text-xs mb-1">
              <span className="font-medium" style={{ color: 'var(--ms-text)' }}>{s.label}</span>
              <span className="flex items-center gap-2">
                {conversion != null && (
                  <span className="text-[10px]" style={{ color: 'var(--ms-text-muted)' }}>{conversion}% →</span>
                )}
                <strong style={{ color: 'var(--ms-text)' }}>{s.value}</strong>
              </span>
            </div>
            <div className="h-6 rounded overflow-hidden" style={{ backgroundColor: 'var(--ms-bg)' }}>
              <div
                className="h-full rounded transition-all flex items-center justify-end pr-2"
                style={{
                  width: `${Math.max(pct, s.value > 0 ? 6 : 0)}%`,
                  backgroundColor: s.color,
                  minWidth: s.value > 0 ? 24 : 0,
                }}
              >
                <span className="text-[10px] font-semibold" style={{ color: '#fff' }}>{pct}%</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
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
  const [period, setPeriod] = useState<PeriodKey>('6m')
  const periodConfig = PERIODS.find(p => p.key === period)!

  const { data, isLoading } = useQuery({ queryKey: ['reports-summary'], queryFn: () => getReportsSummary().then(r => r.data) })
  const { data: trends } = useQuery({
    queryKey: ['reports-trends', periodConfig.months],
    queryFn: () => getReportsTrends(periodConfig.months).then(r => r.data),
  })
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
  if (!data) return <div><PageHeader title="Reports" /><p className="mt-4" style={{ color: 'var(--ms-text-muted)' }}>No report data available.</p></div>

  // Funnel numbers derived from counts + sales_funnel
  const totalJobs = data.counts.jobs
  const quotedJobs = data.sales_funnel.sent_quotes
  const approvedJobs = data.sales_funnel.approved_quotes
  const completedJobs = (data.jobs_by_status.completed ?? 0)
    + (data.jobs_by_status.awaiting_collection ?? 0)
    + (data.jobs_by_status.collected ?? 0)
  const collectedJobs = data.jobs_by_status.collected ?? 0

  return (
    <div>
      <PageHeader
        title="Reports"
        action={
          <div className="flex items-center gap-2">
            <div
              className="inline-flex rounded-lg p-0.5"
              style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border)' }}
            >
              {PERIODS.map(p => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => setPeriod(p.key)}
                  className="px-3 py-1 text-xs font-medium rounded-md transition-colors"
                  style={{
                    backgroundColor: period === p.key ? 'var(--ms-surface)' : 'transparent',
                    color: period === p.key ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
                    boxShadow: period === p.key ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                  }}
                >
                  {p.label}
                </button>
              ))}
            </div>
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
                  style={{ backgroundColor: 'var(--ms-card)', border: '1px solid var(--ms-border)' }}
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
                      style={{ color: 'var(--ms-text)' }}
                      onClick={() => { item.action(); setExportOpen(false) }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <MetricCard label="Revenue" value={formatCents(data.financials.revenue_cents)} icon={DollarSign} iconBg="#E8F5EC" iconColor="#1A6838" />
        <MetricCard label="Cost" value={formatCents(data.financials.cost_cents)} icon={Wallet} iconBg="#F8EDDD" iconColor="#B06010" />
        <MetricCard label="Gross Profit" value={formatCents(data.financials.gross_profit_cents)} icon={Scale} iconBg="#F1E8FB" iconColor="#6040A8" />
        <MetricCard label="Outstanding" value={formatCents(data.financials.outstanding_cents)} icon={BarChart3} iconBg="#FBEAEA" iconColor="#A33838" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-6">
        {/* Sales funnel */}
        <Card className="p-5 xl:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={15} style={{ color: 'var(--ms-accent)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Sales Funnel</h2>
            <span className="text-xs ml-auto" style={{ color: 'var(--ms-text-muted)' }}>
              Approval rate: <strong style={{ color: 'var(--ms-text)' }}>{data.sales_funnel.approval_rate_percent}%</strong>
            </span>
          </div>
          <SalesFunnel
            received={totalJobs}
            quoted={quotedJobs}
            approved={approvedJobs}
            completed={completedJobs}
            collected={collectedJobs}
          />
        </Card>

        {/* KPIs */}
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock size={15} style={{ color: 'var(--ms-accent)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Operations</h2>
          </div>
          <div className="space-y-2.5 text-sm">
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Gross margin</span>
              <strong style={{ color: 'var(--ms-text)' }}>{data.financials.gross_margin_percent}%</strong>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Avg revenue / job</span>
              <strong style={{ color: 'var(--ms-text)' }}>{formatCents(data.operations.avg_revenue_per_job_cents)}</strong>
            </div>
            {data.operations.avg_turnaround_days != null && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--ms-text-muted)' }}>Avg turnaround</span>
                <strong style={{ color: 'var(--ms-text)' }}>{data.operations.avg_turnaround_days}d</strong>
              </div>
            )}
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Quote → invoice</span>
              <strong style={{ color: 'var(--ms-text)' }}>{data.operations.quote_to_invoice_pct}%</strong>
            </div>
            {data.operations.avg_quote_response_hours != null && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--ms-text-muted)' }}>Quote response</span>
                <strong style={{ color: 'var(--ms-text)' }}>{data.operations.avg_quote_response_hours}h</strong>
              </div>
            )}
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Work minutes</span>
              <strong style={{ color: 'var(--ms-text)' }}>{data.operations.work_minutes}</strong>
            </div>
            <div
              className="flex justify-between pt-2 mt-1"
              style={{ borderTop: '1px dashed var(--ms-border)' }}
            >
              <span style={{ color: 'var(--ms-text-muted)' }}>Billed</span>
              <strong style={{ color: 'var(--ms-text)' }}>{formatCents(data.financials.billed_cents)}</strong>
            </div>
          </div>
        </Card>
      </div>

      {/* Trends — vertical bars */}
      {trends && trends.months.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
          <Card className="p-5">
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--ms-text)' }}>Jobs Opened · {periodConfig.label}</h2>
            <VerticalBarChart
              color="var(--ms-accent)"
              data={trends.months.map(m => ({
                label: m.month,
                value: m.jobs_opened,
                display: String(m.jobs_opened),
              }))}
            />
          </Card>
          <Card className="p-5">
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--ms-text)' }}>Revenue · {periodConfig.label}</h2>
            <VerticalBarChart
              color="#1A6838"
              data={trends.months.map(m => ({
                label: m.month,
                value: m.revenue_cents,
                display: m.revenue_cents > 0 ? formatCents(m.revenue_cents) : '$0',
              }))}
            />
          </Card>
        </div>
      )}

      {/* Status distributions */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-6">
        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>Job Status</h2>
          <div className="space-y-2 text-sm">
            {Object.entries(data.jobs_by_status).map(([status, count]) => (
              <div key={status} className="flex justify-between">
                <span className="capitalize" style={{ color: 'var(--ms-text-muted)' }}>{status.replace(/_/g, ' ')}</span>
                <strong style={{ color: 'var(--ms-text)' }}>{count}</strong>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>Quote Status</h2>
          {Object.keys(data.quotes_by_status).length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No quotes sent yet.</p>
          ) : (
            <div className="space-y-2 text-sm">
              {Object.entries(data.quotes_by_status).map(([status, count]) => (
                <div key={status} className="flex justify-between">
                  <span className="capitalize" style={{ color: 'var(--ms-text-muted)' }}>{status.replace(/_/g, ' ')}</span>
                  <strong style={{ color: 'var(--ms-text)' }}>{count}</strong>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-5">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>Service Breakdown</h2>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Watches</span>
              <strong style={{ color: 'var(--ms-text)' }}>{data.counts.watches}</strong>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Watch jobs</span>
              <strong style={{ color: 'var(--ms-text)' }}>{data.counts.jobs}</strong>
            </div>
            {(data.counts.shoe_jobs ?? 0) > 0 && (
              <div className="flex justify-between">
                <span style={{ color: 'var(--ms-text-muted)' }}>Shoe jobs</span>
                <strong style={{ color: 'var(--ms-text)' }}>{data.counts.shoe_jobs}</strong>
              </div>
            )}
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Customers</span>
              <strong style={{ color: 'var(--ms-text)' }}>{data.counts.customers}</strong>
            </div>
            <div className="flex justify-between">
              <span style={{ color: 'var(--ms-text-muted)' }}>Invoices</span>
              <strong style={{ color: 'var(--ms-text)' }}>{data.counts.invoices}</strong>
            </div>
          </div>
        </Card>
      </div>

      {/* Shoe repair section — only if shoe jobs exist */}
      {(data.counts.shoe_jobs ?? 0) > 0 && data.shoe_jobs_by_status && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
          <Card className="p-5">
            <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>Shoe Job Status</h2>
            <div className="space-y-2 text-sm">
              {Object.entries(data.shoe_jobs_by_status).map(([status, count]) => (
                <div key={status} className="flex justify-between">
                  <span className="capitalize" style={{ color: 'var(--ms-text-muted)' }}>{status.replace(/_/g, ' ')}</span>
                  <strong style={{ color: 'var(--ms-text)' }}>{count as number}</strong>
                </div>
              ))}
            </div>
          </Card>
          {data.shoe_quotes && (
            <Card className="p-5">
              <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>Shoe Quote Status</h2>
              <div className="mb-2 text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                Approval rate: <strong style={{ color: 'var(--ms-text)' }}>{data.shoe_quotes.approval_rate_percent}%</strong>
              </div>
              {Object.keys(data.shoe_quotes.by_status).length === 0 ? (
                <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>No shoe quotes sent yet.</p>
              ) : (
                <div className="space-y-2 text-sm">
                  {Object.entries(data.shoe_quotes.by_status).map(([status, count]) => (
                    <div key={status} className="flex justify-between">
                      <span className="capitalize" style={{ color: 'var(--ms-text-muted)' }}>{status.replace(/_/g, ' ')}</span>
                      <strong style={{ color: 'var(--ms-text)' }}>{count as number}</strong>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>
      )}

      {/* Tech leaderboard */}
      {techBreakdown && techBreakdown.length > 0 && (
        <Card className="p-5 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Users size={15} style={{ color: 'var(--ms-accent)' }} />
            <h2 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>Technician Leaderboard</h2>
          </div>
          <div className="space-y-2">
            {[...techBreakdown]
              .sort((a, b) => b.total_minutes - a.total_minutes)
              .map((t, i) => {
                const maxMins = Math.max(...techBreakdown.map(x => x.total_minutes), 1)
                const pct = Math.round((t.total_minutes / maxMins) * 100)
                return (
                  <div key={t.user_id}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="flex items-center gap-2">
                        <span
                          className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-semibold"
                          style={{
                            backgroundColor: i === 0 ? 'var(--ms-accent)' : 'var(--ms-bg)',
                            color: i === 0 ? '#fff' : 'var(--ms-text-muted)',
                          }}
                        >{i + 1}</span>
                        <span style={{ color: 'var(--ms-text)' }}>{t.user_name}</span>
                      </span>
                      <span className="flex gap-3 text-xs">
                        <span style={{ color: 'var(--ms-text-muted)' }}>{t.jobs_count} job{t.jobs_count !== 1 ? 's' : ''}</span>
                        <strong style={{ color: 'var(--ms-text)' }}>{Math.floor(t.total_minutes / 60)}h {t.total_minutes % 60}m</strong>
                      </span>
                    </div>
                    <div className="h-1.5 rounded overflow-hidden" style={{ backgroundColor: 'var(--ms-bg)' }}>
                      <div
                        className="h-full rounded"
                        style={{ width: `${pct}%`, backgroundColor: 'var(--ms-accent)' }}
                      />
                    </div>
                  </div>
                )
              })}
          </div>
        </Card>
      )}

      {activity && activity.length > 0 && (
        <Card className="p-5 mb-6">
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>Audit Log</h2>
          <div className="space-y-1 text-xs max-h-72 overflow-y-auto">
            {activity.map(ev => (
              <div key={ev.id} className="flex items-start gap-3 py-1.5 border-b" style={{ borderColor: 'var(--ms-border)' }}>
                <span
                  className="px-1.5 py-0.5 rounded text-xs font-medium shrink-0 uppercase tracking-wide"
                  style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text-muted)' }}
                >
                  {ev.event_type.replace(/_/g, ' ')}
                </span>
                <span className="flex-1" style={{ color: 'var(--ms-text-mid)' }}>{ev.event_summary}</span>
                <span className="shrink-0" style={{ color: 'var(--ms-text-muted)' }}>
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
