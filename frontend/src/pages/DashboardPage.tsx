import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Wrench, Users, DollarSign, Clock } from 'lucide-react'
import { listJobs, listCustomers } from '@/lib/api'
import { Card, PageHeader, Badge, Spinner } from '@/components/ui'
import { formatCents, formatDate } from '@/lib/utils'
import { Link } from 'react-router-dom'

const CLOSED_JOB_STATUSES = ['no_go', 'completed', 'awaiting_collection', 'collected']
// Jobs where customer gave the go-ahead — these represent outstanding revenue
const GO_AHEAD_STATUSES = ['go_ahead', 'parts_to_order', 'sent_to_labanda', 'quoted_by_labanda', 'awaiting_parts', 'working_on', 'service', 'completed', 'awaiting_collection']

// Status breakdown order for "active" (non-closed, non-collected) jobs
const BREAKDOWN_STATUSES = [
  'awaiting_quote',
  'awaiting_go_ahead',
  'go_ahead',
  'parts_to_order',
  'sent_to_labanda',
  'quoted_by_labanda',
  'awaiting_parts',
  'working_on',
  'completed',
  'awaiting_collection',
] as const

const STAT_STYLES = [
  { iconBg: '#F5E8CC', iconColor: '#9B7228', label: 'Open Jobs' },
  { iconBg: '#DFF0EC', iconColor: '#2A6B65', label: 'Customers' },
  { iconBg: '#F5E8E8', iconColor: '#8B3A3A', label: 'Awaiting Go-Ahead' },
  { iconBg: '#E8F0E4', iconColor: '#3B6B42', label: 'Outstanding' },
]

const KPI_ANIM_CSS = `
@keyframes kpiRise {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
.kpi-card { animation: kpiRise 0.48s cubic-bezier(0.22, 1, 0.36, 1) both; }
`

function StatCard({
  label, value, icon: Icon, iconBg, iconColor, index,
}: {
  label: string; value: number; icon: React.ElementType; iconBg: string; iconColor: string; index: number
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      className="kpi-card p-6 flex items-center gap-5"
      style={{
        backgroundColor: 'var(--cafe-surface)',
        border: '1px solid var(--cafe-border)',
        borderRadius: 20,
        boxShadow: hovered
          ? '0 4px 8px rgba(80,50,15,0.10), 0 14px 36px rgba(80,50,15,0.13)'
          : '0 1px 3px rgba(80,50,15,0.06), 0 4px 18px rgba(80,50,15,0.09)',
        transform: hovered ? 'translateY(-3px)' : 'translateY(0)',
        transition: 'transform 0.22s ease, box-shadow 0.22s ease',
        animationDelay: `${index * 0.07}s`,
        cursor: 'default',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
        style={{
          backgroundColor: iconBg,
          boxShadow: `inset 0 1px 2px rgba(255,255,255,0.55), 0 2px 6px ${iconBg}`,
        }}
      >
        <Icon size={22} style={{ color: iconColor }} />
      </div>
      <div>
        <p
          className="leading-none"
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            color: 'var(--cafe-text)',
            fontSize: '2.1rem',
            fontWeight: 700,
            letterSpacing: '-0.02em',
          }}
        >
          {value}
        </p>
        <p className="text-xs mt-1.5 tracking-wide uppercase font-medium" style={{ color: 'var(--cafe-text-muted)' }}>
          {label}
        </p>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { data: jobs, isLoading: jobsLoading } = useQuery({ queryKey: ['jobs'], queryFn: () => listJobs().then(r => r.data) })
  const { data: customers } = useQuery({ queryKey: ['customers'], queryFn: () => listCustomers().then(r => r.data) })

  const openJobs = jobs?.filter(j => !CLOSED_JOB_STATUSES.includes(j.status)) ?? []
  const awaitingGoAheadJobs = jobs?.filter(j => j.status === 'awaiting_go_ahead') ?? []
  const goAheadJobs = jobs?.filter(j => GO_AHEAD_STATUSES.includes(j.status)) ?? []
  const outstandingTotal = goAheadJobs.reduce((s, j) => s + (j.cost_cents > 0 ? j.cost_cents : j.pre_quote_cents), 0)

  if (jobsLoading) return <Spinner />

  return (
    <div>
      <style>{KPI_ANIM_CSS}</style>
      <PageHeader title="Overview" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label={STAT_STYLES[0].label} value={openJobs.length}              icon={Wrench}      iconBg={STAT_STYLES[0].iconBg} iconColor={STAT_STYLES[0].iconColor} index={0} />
        <StatCard label={STAT_STYLES[1].label} value={customers?.length ?? 0}       icon={Users}       iconBg={STAT_STYLES[1].iconBg} iconColor={STAT_STYLES[1].iconColor} index={1} />
        <StatCard label={STAT_STYLES[2].label} value={awaitingGoAheadJobs.length}   icon={Clock}       iconBg={STAT_STYLES[2].iconBg} iconColor={STAT_STYLES[2].iconColor} index={2} />
        <StatCard label={STAT_STYLES[3].label} value={goAheadJobs.length}           icon={DollarSign}  iconBg={STAT_STYLES[3].iconBg} iconColor={STAT_STYLES[3].iconColor} index={3} />
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

        {/* Status Breakdown */}
        <Card>
          <div
            className="flex items-center justify-between px-5 py-4"
            style={{ borderBottom: '1px solid var(--cafe-border)' }}
          >
            <h2
              className="font-semibold flex items-center gap-2"
              style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }}
            >
              <DollarSign size={16} style={{ color: 'var(--cafe-gold-dark)' }} />
              Jobs by Status
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
            {BREAKDOWN_STATUSES.map((status, i) => {
              const count = (jobs ?? []).filter(j => j.status === status).length
              if (count === 0) return null
              const isGoAhead = GO_AHEAD_STATUSES.includes(status)
              return (
                <Link
                  key={status}
                  to={`/jobs?status=${status}`}
                  className="flex items-center justify-between px-5 py-3 transition-colors"
                  style={{ borderBottom: i < BREAKDOWN_STATUSES.length - 1 ? '1px solid var(--cafe-border)' : 'none' }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#F5EDE0')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <div className="flex items-center gap-3">
                    <Badge status={status} />
                    {isGoAhead && (
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded" style={{ backgroundColor: '#E8F0E4', color: '#3B6B42' }}>
                        outstanding
                      </span>
                    )}
                  </div>
                  <span className="text-sm font-semibold" style={{ color: 'var(--cafe-text)' }}>{count}</span>
                </Link>
              )
            })}
            {(jobs ?? []).filter(j => !CLOSED_JOB_STATUSES.includes(j.status)).length === 0 && (
              <p className="px-5 py-8 text-sm italic" style={{ color: 'var(--cafe-text-muted)', fontFamily: "'Playfair Display', Georgia, serif" }}>
                No active jobs
              </p>
            )}
          </div>
          {outstandingTotal > 0 && (
            <div
              className="px-5 py-3 flex justify-between items-center"
              style={{ borderTop: '1px solid var(--cafe-border)' }}
            >
              <span className="text-xs font-medium tracking-wide uppercase" style={{ color: 'var(--cafe-text-muted)' }}>
                Total outstanding ({goAheadJobs.length} jobs)
              </span>
              <span className="text-sm font-bold" style={{ color: 'var(--cafe-text)' }}>{formatCents(outstandingTotal)}</span>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
