import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { formatTenantLabel, getParentShopBookingsReport } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, Input, PageHeader, Select, Spinner } from '@/components/ui'
import { defaultReportFromDate, defaultReportToDate, toIsoEnd, toIsoStart } from './dateRange'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'declined', label: 'Declined' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'expired', label: 'Expired' },
]

export default function MinitShopReportsPage() {
  const [fromYmd, setFromYmd] = useState(defaultReportFromDate)
  const [toYmd, setToYmd] = useState(defaultReportToDate)
  const [status, setStatus] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['minit-shop-bookings-report', fromYmd, toYmd, status],
    queryFn: () =>
      getParentShopBookingsReport({
        from_date: toIsoStart(fromYmd),
        to_date: toIsoEnd(toYmd),
        status: status || undefined,
        limit: 200,
      }).then(r => r.data),
  })

  return (
    <div>
      <PageHeader title="Shop reports" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Booking volume and status breakdown across all retail shops in the network.
      </p>

      <Card className="p-5 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <Input label="From" type="date" value={fromYmd} onChange={e => setFromYmd(e.target.value)} className="w-40" />
          <Input label="To" type="date" value={toYmd} onChange={e => setToYmd(e.target.value)} className="w-40" />
          <Select label="Status" value={status} onChange={e => setStatus(e.target.value)} className="w-44">
            {STATUS_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </Select>
        </div>
      </Card>

      {isLoading || !data ? (
        <Spinner />
      ) : (
        <>
          <Card className="p-5 mb-6">
            <p className="text-sm font-semibold mb-3" style={{ color: 'var(--ms-text)' }}>
              Network totals ({data.totals.total} bookings)
            </p>
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              {data.totals.accepted} accepted · {data.totals.pending} pending · {data.totals.declined} declined ·{' '}
              {data.totals.expired} expired · {data.totals.cancelled} cancelled
            </p>
            {data.shops_under_goal != null && (
              <p className="text-sm mt-2" style={{ color: 'var(--ms-text-muted)' }}>
                {data.shops_under_goal} shop{data.shops_under_goal === 1 ? '' : 's'} under {data.weekly_goal ?? 1} booking a week
                {data.totals.avg_response_minutes != null && ` · operators answer in ${data.totals.avg_response_minutes} min on average`}
              </p>
            )}
          </Card>

          <Card className="mb-6 overflow-hidden">
            <div className="px-5 py-3 font-semibold text-sm" style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}>
              By shop
            </div>
            {(data.by_shop ?? []).length === 0 ? (
              <p className="px-5 py-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No bookings in range.</p>
            ) : (
              (data.by_shop ?? []).map(row => (
                <div
                  key={row.tenant_id}
                  className="px-5 py-3 flex justify-between gap-4 text-sm"
                  style={{ borderBottom: '1px solid var(--ms-border)' }}
                >
                  <span style={{ color: 'var(--ms-text)' }}>{formatTenantLabel(row.tenant_name, row.shop_number)}</span>
                  <span style={{ color: row.under_weekly_goal ? 'var(--ms-danger, #b42318)' : 'var(--ms-text-muted)' }}>
                    {row.total} total ({row.accepted} accepted, {row.pending} pending)
                    {row.per_week != null && ` · ${row.per_week}/week`}
                    {row.under_weekly_goal && ' · under goal'}
                  </span>
                </div>
              ))
            )}
          </Card>

          {(data.by_operator ?? []).length > 0 && (
            <Card className="mb-6 overflow-hidden">
              <div className="px-5 py-3 font-semibold text-sm" style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}>
                Operator response times
              </div>
              {(data.by_operator ?? []).map(op => (
                <div
                  key={op.tenant_id}
                  className="px-5 py-3 flex justify-between gap-4 text-sm"
                  style={{ borderBottom: '1px solid var(--ms-border)' }}
                >
                  <span style={{ color: 'var(--ms-text)' }}>{formatTenantLabel(op.tenant_name, op.shop_number)}</span>
                  <span style={{ color: 'var(--ms-text-muted)' }}>
                    {op.offered} offered · {op.responded} answered
                    {op.avg_response_minutes != null && ` (avg ${op.avg_response_minutes} min)`}
                    {op.moved_to_pool > 0 && ` · ${op.moved_to_pool} to pool`}
                  </span>
                </div>
              ))}
            </Card>
          )}

          <Card className="overflow-hidden">
            <div className="px-5 py-3 font-semibold text-sm" style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}>
              Recent bookings
            </div>
            {(data.bookings ?? []).length === 0 ? (
              <p className="px-5 py-4 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No rows.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                      <th className="text-left px-5 py-2 font-medium">Date</th>
                      <th className="text-left px-5 py-2 font-medium">Shop</th>
                      <th className="text-left px-5 py-2 font-medium">Operator</th>
                      <th className="text-left px-5 py-2 font-medium">Customer</th>
                      <th className="text-left px-5 py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.bookings ?? []).map(b => (
                      <tr key={b.id} style={{ borderBottom: '1px solid var(--ms-border)' }}>
                        <td className="px-5 py-2 whitespace-nowrap">{formatDate(b.created_at)}</td>
                        <td className="px-5 py-2">{formatTenantLabel(b.requesting_shop_name, b.requesting_shop_number)}</td>
                        <td className="px-5 py-2">{formatTenantLabel(b.target_operator_name, b.target_operator_shop_number)}</td>
                        <td className="px-5 py-2">{b.customer_name}</td>
                        <td className="px-5 py-2 capitalize">{b.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}

