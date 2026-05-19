import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock,
  Inbox,
  KeyRound,
  TrendingUp,
} from 'lucide-react'
import {
  formatTenantLabel,
  getParentOperationsOverview,
  type ParentDashboardBookingSnippet,
  type ParentOperationsOverview,
  type ParentTroubleshootingItem,
} from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, PageHeader } from '@/components/ui'

function relativeTime(iso: string) {
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  if (diff < 60_000) return 'Just now'
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`
  return formatDate(iso)
}

function statusStyle(status: string): { bg: string; color: string; label: string } {
  switch (status) {
    case 'pending':
      return { bg: 'rgba(180,120,40,0.15)', color: '#B47828', label: 'Pending' }
    case 'accepted':
      return { bg: 'rgba(40,120,80,0.12)', color: '#2D7A52', label: 'Accepted' }
    case 'declined':
      return { bg: 'rgba(201,106,90,0.12)', color: '#C96A5A', label: 'Declined' }
    case 'cancelled':
      return { bg: 'var(--ms-border)', color: 'var(--ms-text-muted)', label: 'Cancelled' }
    case 'expired':
      return { bg: 'var(--ms-border)', color: 'var(--ms-text-muted)', label: 'Expired' }
    default:
      return { bg: 'var(--ms-border)', color: 'var(--ms-text-muted)', label: status }
  }
}

function MetricCard({
  label,
  value,
  sub,
  accent,
  to,
}: {
  label: string
  value: string | number
  sub: string
  accent?: boolean
  to?: string
}) {
  const inner = (
    <Card
      className="p-5 h-full"
      style={accent ? { borderColor: 'var(--ms-accent)', borderWidth: 1 } : undefined}
    >
      <p className="text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
        {label}
      </p>
      <p className="text-3xl font-bold mt-2 tabular-nums" style={{ color: accent ? 'var(--ms-accent)' : 'var(--ms-text)' }}>
        {value}
      </p>
      <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
        {sub}
      </p>
    </Card>
  )
  if (!to) return inner
  return (
    <Link to={to} className="block hover:opacity-95 transition-opacity">
      {inner}
    </Link>
  )
}

function AttentionRow({ item }: { item: ParentTroubleshootingItem }) {
  const isWarning = item.severity === 'warning'
  return (
    <div
      className="px-4 py-3 flex gap-3 items-start"
      style={{ borderBottom: '1px solid var(--ms-border)' }}
    >
      <AlertTriangle
        size={16}
        className="shrink-0 mt-0.5"
        style={{ color: isWarning ? '#C96A5A' : 'var(--ms-text-muted)' }}
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
          {item.title}
        </p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
          {item.detail}
        </p>
        {item.created_at && (
          <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
            {relativeTime(item.created_at)}
          </p>
        )}
      </div>
    </div>
  )
}

function BookingRow({ booking }: { booking: ParentDashboardBookingSnippet }) {
  const st = statusStyle(booking.status)
  return (
    <div
      className="px-4 py-3 flex flex-wrap items-center gap-3 justify-between"
      style={{ borderBottom: '1px solid var(--ms-border)' }}
    >
      <div className="min-w-0">
        <p className="text-sm font-medium truncate" style={{ color: 'var(--ms-text)' }}>
          {booking.customer_name}
        </p>
        <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--ms-text-muted)' }}>
          {formatTenantLabel(booking.requesting_shop_name, booking.requesting_shop_number)}
          {' → '}
          {booking.target_operator_name}
          {booking.region ? ` · ${booking.region}` : ''}
        </p>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <span
          className="text-xs font-semibold px-2 py-0.5 rounded-full"
          style={{ backgroundColor: st.bg, color: st.color }}
        >
          {st.label}
        </span>
        <span className="text-xs tabular-nums" style={{ color: 'var(--ms-text-muted)' }}>
          {relativeTime(booking.created_at)}
        </span>
      </div>
    </div>
  )
}

function needsAttentionCount(data: ParentOperationsOverview) {
  return (
    data.pending_bookings
    + data.stale_pending_count
    + data.problem_bookings_7d
    + data.operators_missing_dispatch_phone
  )
}

function DashboardSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map(i => (
          <Card key={i} className="h-24" style={{ backgroundColor: 'var(--ms-border)' }} />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="h-64" style={{ backgroundColor: 'var(--ms-border)' }} />
        <Card className="h-64" style={{ backgroundColor: 'var(--ms-border)' }} />
      </div>
    </div>
  )
}

export default function MinitOperationsPage() {
  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ['minit-operations-overview'],
    queryFn: () => getParentOperationsOverview().then(r => r.data),
    staleTime: 120_000,
    refetchInterval: 60_000,
  })

  if (isError || (!isLoading && !data)) {
    return (
      <div>
        <PageHeader title="Dashboard" />
        <p className="text-sm" style={{ color: '#C96A5A' }}>
          Could not load dashboard. Confirm you are signed in as Minit HQ (mmsupport).
        </p>
      </div>
    )
  }

  if (isLoading || !data) {
    return (
      <div>
        <PageHeader title="Dashboard" />
        <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
          Loading network overview…
        </p>
        <DashboardSkeleton />
      </div>
    )
  }

  const attentionCount = needsAttentionCount(data)
  const activePct =
    data.retail_shop_count > 0
      ? Math.round((1 - data.shops_without_recent_booking / data.retail_shop_count) * 100)
      : 0

  return (
    <div>
      <PageHeader title="Dashboard" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Network operations for {data.retail_shop_count} shops and {data.operator_count} mobile operators.
        {isFetching && <span className="ml-2 opacity-70">Updating…</span>}
      </p>

      {attentionCount > 0 && (
        <Card
          className="mb-6 p-4 flex flex-wrap items-center justify-between gap-3"
          style={{ borderColor: '#C96A5A', backgroundColor: 'rgba(201,106,90,0.06)' }}
        >
          <div className="flex items-start gap-3">
            <AlertTriangle size={22} style={{ color: '#C96A5A', flexShrink: 0 }} />
            <div>
              <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>
                {attentionCount} item{attentionCount === 1 ? '' : 's'} need attention
              </p>
              <p className="text-sm mt-0.5" style={{ color: 'var(--ms-text-muted)' }}>
                {data.pending_bookings > 0 && `${data.pending_bookings} pending`}
                {data.stale_pending_count > 0 && ` · ${data.stale_pending_count} stale (>7d)`}
                {data.problem_bookings_7d > 0 && ` · ${data.problem_bookings_7d} failed this week`}
                {data.operators_missing_dispatch_phone > 0
                  && ` · ${data.operators_missing_dispatch_phone} operators missing SMS`}
              </p>
            </div>
          </div>
          <Link
            to="/minit/mobile-services"
            className="inline-flex items-center gap-1.5 text-sm font-medium px-3 py-2 rounded-lg"
            style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
          >
            Mobile Services
            <ArrowRight size={16} />
          </Link>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-6">
        <MetricCard
          label="Pending bookings"
          value={data.pending_bookings}
          sub={data.stale_pending_count > 0 ? `${data.stale_pending_count} waiting over 7 days` : 'Awaiting operator response'}
          accent={data.pending_bookings > 0}
          to="/minit/mobile-services"
        />
        <MetricCard
          label="Bookings this week"
          value={data.bookings_7d}
          sub={`${data.accepted_7d} accepted · ${data.declined_7d} declined`}
          to="/minit/reports"
        />
        <MetricCard
          label="Acceptance rate (7d)"
          value={data.acceptance_rate_7d != null ? `${data.acceptance_rate_7d}%` : '—'}
          sub="Of resolved requests (accepted vs declined/cancelled/expired)"
          to="/minit/reports"
        />
        <MetricCard
          label="Active mobile jobs"
          value={data.active_mobile_jobs}
          sub="In progress across operators"
          to="/minit/mobile-services"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 mb-8">
        <MetricCard
          label="Shops active (30d)"
          value={`${activePct}%`}
          sub={`${data.retail_shop_count - data.shops_without_recent_booking} of ${data.retail_shop_count} sent a booking`}
          to="/minit/reports/shops"
        />
        <MetricCard
          label="Bookings (30d)"
          value={data.bookings_30d}
          sub={`${data.accepted_30d} accepted network-wide`}
          to="/minit/reports"
        />
        <MetricCard
          label="Quiet shops (30d)"
          value={data.shops_without_recent_booking}
          sub="No booking requests this month"
          to="/minit/shops"
        />
        <MetricCard
          label="Retail shops"
          value={data.retail_shop_count}
          sub={`${data.operator_count} mobile operators`}
          to="/minit/shops"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        <Card className="overflow-hidden">
          <div
            className="px-5 py-3 flex items-center justify-between"
            style={{ borderBottom: '1px solid var(--ms-border)' }}
          >
            <h2 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
              Activity by region (30 days)
            </h2>
            <TrendingUp size={16} style={{ color: 'var(--ms-accent)' }} />
          </div>
          {data.region_stats.length === 0 ? (
            <p className="p-5 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              No regional data yet. Import shops with Region/Area columns or create bookings.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                    <th className="text-left font-medium px-4 py-2">Region</th>
                    <th className="text-right font-medium px-3 py-2">Shops</th>
                    <th className="text-right font-medium px-3 py-2">Active</th>
                    <th className="text-right font-medium px-3 py-2">Bookings</th>
                    <th className="text-right font-medium px-4 py-2">Pending</th>
                  </tr>
                </thead>
                <tbody>
                  {data.region_stats.map(row => (
                    <tr key={row.region} style={{ borderBottom: '1px solid var(--ms-border)' }}>
                      <td className="px-4 py-2.5 font-medium" style={{ color: 'var(--ms-text)' }}>
                        {row.region}
                      </td>
                      <td className="text-right px-3 py-2.5 tabular-nums" style={{ color: 'var(--ms-text-muted)' }}>
                        {row.shop_count}
                      </td>
                      <td className="text-right px-3 py-2.5 tabular-nums" style={{ color: 'var(--ms-text-muted)' }}>
                        {row.active_shops_30d}
                      </td>
                      <td className="text-right px-3 py-2.5 tabular-nums" style={{ color: 'var(--ms-text)' }}>
                        {row.bookings_30d}
                      </td>
                      <td
                        className="text-right px-4 py-2.5 tabular-nums font-medium"
                        style={{ color: row.pending > 0 ? 'var(--ms-accent)' : 'var(--ms-text-muted)' }}
                      >
                        {row.pending}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="overflow-hidden flex flex-col" style={{ maxHeight: 'min(70vh, 420px)' }}>
          <div
            className="px-5 py-3 shrink-0 flex items-center justify-between"
            style={{ borderBottom: '1px solid var(--ms-border)' }}
          >
            <h2 className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
              Needs attention
            </h2>
            <Link to="/minit/reports" className="text-xs font-medium" style={{ color: 'var(--ms-accent)' }}>
              All reports
            </Link>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto">
            {data.attention_items.length === 0 ? (
              <div className="p-5 flex items-center gap-2 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
                <CheckCircle2 size={18} style={{ color: '#2D7A52' }} />
                Nothing urgent right now.
              </div>
            ) : (
              data.attention_items.map((item, i) => (
                <AttentionRow key={`${item.kind}-${item.related_id ?? item.tenant_id ?? i}`} item={item} />
              ))
            )}
            {data.shops_without_recent_booking > 0 && data.attention_items.every(i => i.kind !== 'shops_quiet_summary') && (
              <div className="px-4 py-3 text-xs" style={{ color: 'var(--ms-text-muted)', borderTop: '1px solid var(--ms-border)' }}>
                {data.shops_without_recent_booking} shops have not booked in 30 days — see{' '}
                <Link to="/minit/reports/shops" className="underline" style={{ color: 'var(--ms-accent)' }}>
                  Shop reports
                </Link>
                .
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden mb-8">
        <div
          className="px-5 py-3 flex flex-wrap items-center justify-between gap-2"
          style={{ borderBottom: '1px solid var(--ms-border)' }}
        >
          <h2 className="text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--ms-text)' }}>
            <Clock size={16} style={{ color: 'var(--ms-accent)' }} />
            Recent booking requests
          </h2>
          <Link to="/minit/reports" className="text-xs font-medium" style={{ color: 'var(--ms-accent)' }}>
            View all
          </Link>
        </div>
        {data.recent_bookings.length === 0 ? (
          <p className="p-5 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
            No booking requests yet. Shops submit mobile service requests from their booking screen.
          </p>
        ) : (
          data.recent_bookings.map(b => <BookingRow key={b.id} booking={b} />)
        )}
      </Card>

      <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>
        Go to
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { to: '/minit/shops', icon: Building2, label: 'Shops' },
          { to: '/minit/mobile-services', icon: KeyRound, label: 'Mobile Services' },
          { to: '/minit/inbox', icon: Inbox, label: 'Inbox' },
          { to: '/minit/accounts', icon: Building2, label: 'Accounts' },
        ].map(({ to, icon: Icon, label }) => (
          <Link
            key={to}
            to={to}
            className="flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors"
            style={{
              backgroundColor: 'var(--ms-surface)',
              border: '1px solid var(--ms-border)',
              color: 'var(--ms-text)',
            }}
          >
            <Icon size={18} style={{ color: 'var(--ms-accent)' }} />
            {label}
          </Link>
        ))}
      </div>
    </div>
  )
}
