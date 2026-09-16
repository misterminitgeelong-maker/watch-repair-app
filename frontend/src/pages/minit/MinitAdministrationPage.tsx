import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, KeyRound, ShieldCheck, Store } from 'lucide-react'
import {
  formatTenantLabel,
  getMinitAdministrationReport,
  type MinitShopAccessRow,
} from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { useMinitHqEnterShop } from '@/lib/adminImpersonation'
import { Badge, Button, Card, PageHeader, Select, Spinner } from '@/components/ui'

type Filter = 'all' | 'shared' | 'own' | 'pending' | 'expired' | 'inactive'

const FILTER_LABELS: Record<Filter, string> = {
  all: 'All shops',
  shared: "On HQ's credential",
  own: 'Own login',
  pending: 'Invite pending',
  expired: 'Invite expired',
  inactive: 'Deactivated',
}

function matches(row: MinitShopAccessRow, filter: Filter): boolean {
  switch (filter) {
    case 'shared':
      return !row.has_own_login
    case 'own':
      return row.has_own_login
    case 'pending':
      return row.invite_status === 'pending'
    case 'expired':
      return row.invite_status === 'expired'
    case 'inactive':
      return !row.is_active
    default:
      return true
  }
}

function StatCard({
  icon: Icon,
  value,
  label,
  hint,
  alert,
}: {
  icon: typeof Store
  value: number
  label: string
  hint?: string
  alert?: boolean
}) {
  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <div
          className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center"
          style={{
            backgroundColor: alert ? 'var(--ms-badge-alert-bg, rgba(185,28,28,0.12))' : 'rgba(79,130,201,0.12)',
            color: alert ? 'var(--ms-badge-alert-text, #b91c1c)' : 'var(--ms-accent)',
          }}
        >
          <Icon size={18} />
        </div>
        <div className="min-w-0">
          <p className="text-2xl font-semibold tabular-nums" style={{ color: 'var(--ms-text)' }}>
            {value}
          </p>
          <p className="text-sm font-medium" style={{ color: 'var(--ms-text)' }}>
            {label}
          </p>
          {hint && (
            <p className="text-xs mt-1" style={{ color: 'var(--ms-text-muted)' }}>
              {hint}
            </p>
          )}
        </div>
      </div>
    </Card>
  )
}

function AccessBadge({ row }: { row: MinitShopAccessRow }) {
  if (!row.is_active) return <Badge variant="danger">Deactivated</Badge>
  if (row.has_own_login) return <Badge variant="success">Own login</Badge>
  if (row.invite_status === 'pending') return <Badge variant="warning">Invite pending</Badge>
  if (row.invite_status === 'expired') return <Badge variant="danger">Invite expired</Badge>
  return <Badge variant="warning">HQ credential</Badge>
}

export default function MinitAdministrationPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const { enterShop, entering, error: enterError } = useMinitHqEnterShop()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['minit-administration'],
    queryFn: () => getMinitAdministrationReport().then(r => r.data),
  })

  const shops = useMemo(
    () => (data?.shops ?? []).filter(row => matches(row, filter)),
    [data?.shops, filter],
  )

  if (isLoading) return <Spinner />

  // Rendering the zeros from a failed fetch would say "every shop has its own
  // login" -- the exact opposite of what an unknown state means here.
  if (isError || !data) {
    return (
      <div>
        <PageHeader title="Administration" />
        <Card className="p-6 text-sm" role="alert" style={{ color: 'var(--ms-text-muted)' }}>
          Could not load the administration report. Refresh to try again.
        </Card>
      </div>
    )
  }

  const report = data
  const sessions = report?.recent_support_sessions ?? []

  return (
    <div>
      <PageHeader title="Administration" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Who can get into each shop in the network, and whether HQ still holds the keys. The other
        reports cover how shops are trading; this one covers access.
      </p>

      {enterError && (
        <p className="text-sm mb-4" style={{ color: 'var(--ms-badge-alert-text, #b91c1c)' }} role="alert">
          {enterError}
        </p>
      )}

      <div
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-6"
        role="group"
        aria-label="Network access summary"
      >
        <StatCard icon={Store} value={report?.shop_total ?? 0} label="Shops in network" />
        <StatCard
          icon={KeyRound}
          value={report?.shared_credential_count ?? 0}
          label="On HQ's credential"
          hint="Not yet handed over — one credential opens all of these."
          alert={(report?.shared_credential_count ?? 0) > 0}
        />
        <StatCard
          icon={ShieldCheck}
          value={report?.own_login_count ?? 0}
          label="Own login"
          hint="Shops that have completed an invite."
        />
        <StatCard
          icon={AlertTriangle}
          value={(report?.invite_pending_count ?? 0) + (report?.invite_expired_count ?? 0)}
          label="Invites outstanding"
          hint={`${report?.invite_pending_count ?? 0} pending · ${report?.invite_expired_count ?? 0} expired`}
          alert={(report?.invite_expired_count ?? 0) > 0}
        />
      </div>

      <div className="mb-4 w-full sm:w-64">
        <Select
          label="Show"
          value={filter}
          onChange={e => setFilter(e.target.value as Filter)}
          aria-label="Filter shops by access state"
        >
          {(Object.keys(FILTER_LABELS) as Filter[]).map(key => (
            <option key={key} value={key}>
              {FILTER_LABELS[key]}
            </option>
          ))}
        </Select>
      </div>

      {shops.length === 0 ? (
        <Card className="p-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          No shops match this filter.
        </Card>
      ) : (
        <Card className="overflow-hidden mb-6">
          <div role="list" aria-label="Shops">
          {shops.map((row, i) => (
            <div
              key={row.tenant_id}
              role="listitem"
              className="px-4 py-3 flex flex-wrap items-center justify-between gap-3"
              style={{ borderTop: i === 0 ? undefined : '1px solid var(--ms-border)' }}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-medium text-sm truncate" style={{ color: 'var(--ms-text)' }}>
                    {formatTenantLabel(row.tenant_name, row.shop_number)}
                  </p>
                  <AccessBadge row={row} />
                </div>
                <p className="text-xs mt-0.5 truncate" style={{ color: 'var(--ms-text-muted)' }}>
                  {row.owner_email ?? 'No owner account'}
                  {row.region?.trim() ? ` · ${row.region}` : ''}
                  {row.last_support_entry_at
                    ? ` · last opened by HQ ${formatDate(row.last_support_entry_at)}`
                    : ''}
                </p>
              </div>
              <Button
                variant="secondary"
                className="shrink-0 text-xs px-2.5 py-1.5"
                disabled={entering === row.tenant_id || !row.is_active}
                onClick={() => void enterShop(row.tenant_id)}
                aria-label={`Open ${formatTenantLabel(row.tenant_name, row.shop_number)}`}
              >
                {entering === row.tenant_id ? 'Opening…' : 'Open'}
              </Button>
            </div>
          ))}
          </div>
        </Card>
      )}

      <h2 className="font-semibold text-base mb-2" style={{ color: 'var(--ms-text)' }}>
        Recent support sessions
      </h2>
      <p className="text-sm mb-3" style={{ color: 'var(--ms-text-muted)' }}>
        Every time an administrator opens a shop it is recorded here and in that shop's own activity
        log.
      </p>
      {sessions.length === 0 ? (
        <Card className="p-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>
          No administrator has opened a shop yet.
        </Card>
      ) : (
        <Card className="overflow-hidden">
          {sessions.map((s, i) => (
            <div
              key={`${s.tenant_id}-${s.created_at}-${i}`}
              className="px-4 py-3 flex flex-wrap items-baseline justify-between gap-2"
              style={{ borderTop: i === 0 ? undefined : '1px solid var(--ms-border)' }}
            >
              <p className="text-sm" style={{ color: 'var(--ms-text)' }}>
                {formatTenantLabel(s.tenant_name, s.shop_number)}
              </p>
              <p className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>
                {s.actor_email ?? 'Unknown administrator'} · {formatDate(s.created_at)}
              </p>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
