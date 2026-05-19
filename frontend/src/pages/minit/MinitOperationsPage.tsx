import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Building2, BarChart3, KeyRound, Wrench } from 'lucide-react'
import { getParentOperationsOverview } from '@/lib/api'
import { Card, PageHeader, Spinner } from '@/components/ui'

function KpiCard({
  label,
  value,
  hint,
  to,
}: {
  label: string
  value: number
  hint: string
  to?: string
}) {
  const inner = (
    <Card className="p-5 h-full">
      <p className="text-xs font-medium uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>
        {label}
      </p>
      <p className="text-3xl font-bold mt-2" style={{ color: 'var(--ms-text)' }}>
        {value}
      </p>
      <p className="text-sm mt-1" style={{ color: 'var(--ms-text-muted)' }}>
        {hint}
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

function QuickLink({ to, icon: Icon, label }: { to: string; icon: typeof Building2; label: string }) {
  return (
    <Link
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
  )
}

export default function MinitOperationsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['minit-operations-overview'],
    queryFn: () => getParentOperationsOverview().then(r => r.data),
  })

  if (isLoading) return <Spinner />
  if (isError || !data) {
    return (
      <div>
        <PageHeader title="Operations" />
        <p className="text-sm" style={{ color: '#C96A5A' }}>
          Could not load operations overview. Confirm you are signed in as Minit HQ (mmsupport).
        </p>
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="Operations" />
      <p className="text-sm mb-6" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Network control centre for shop bookings and mobile services across {data.retail_shop_count} shops and{' '}
        {data.operator_count} operators.
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 mb-8">
        <KpiCard
          label="Pending bookings"
          value={data.pending_bookings}
          hint="Awaiting operator accept/decline"
          to="/minit/troubleshooting"
        />
        <KpiCard
          label="Active mobile jobs"
          value={data.active_mobile_jobs}
          hint="In progress across the network"
          to="/minit/reports/mobile"
        />
        <KpiCard
          label="Shops quiet (30d)"
          value={data.shops_without_recent_booking}
          hint="No booking requests this month"
          to="/minit/reports/shops"
        />
        <KpiCard
          label="Problem bookings (7d)"
          value={data.problem_bookings_7d}
          hint="Declined, cancelled, or expired"
          to="/minit/troubleshooting"
        />
        <KpiCard
          label="Operators missing SMS"
          value={data.operators_missing_dispatch_phone}
          hint="No dispatch phone for booking alerts"
          to="/minit/troubleshooting"
        />
        <KpiCard label="Retail shops" value={data.retail_shop_count} hint="Linked booking-only sites" to="/minit/shops" />
      </div>

      <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>
        Quick links
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <QuickLink to="/minit/shops" icon={Building2} label="Shop control" />
        <QuickLink to="/minit/reports/shops" icon={BarChart3} label="Shop reports" />
        <QuickLink to="/minit/reports/mobile" icon={KeyRound} label="Mobile reports" />
        <QuickLink to="/minit/troubleshooting" icon={Wrench} label="Troubleshooting" />
        <QuickLink to="/shop-mobile-bookings" icon={AlertTriangle} label="Test booking" />
        <QuickLink to="/parent-account" icon={Building2} label="Lead routing" />
      </div>
    </div>
  )
}
