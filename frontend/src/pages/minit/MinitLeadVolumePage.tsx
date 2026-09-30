import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getParentLeadVolumeReport, type LeadVolumeBucket } from '@/lib/api'
import { Card, PageHeader, Spinner } from '@/components/ui'

type Period = 'daily' | 'weekly' | 'monthly'

const PERIODS: { key: Period; label: string; column: string }[] = [
  { key: 'daily', label: 'Daily (30 days)', column: 'Day' },
  { key: 'weekly', label: 'Weekly (12 weeks)', column: 'Week starting' },
  { key: 'monthly', label: 'Monthly (12 months)', column: 'Month' },
]

function formatPeriod(period: Period, ymd: string) {
  const d = new Date(`${ymd}T00:00:00`)
  return period === 'monthly'
    ? d.toLocaleDateString('en-AU', { month: 'short', year: 'numeric' })
    : d.toLocaleDateString('en-AU', { weekday: period === 'daily' ? 'short' : undefined, day: 'numeric', month: 'short' })
}

export default function MinitLeadVolumePage() {
  const [period, setPeriod] = useState<Period>('daily')
  const { data, isLoading, isError } = useQuery({
    queryKey: ['minit-lead-volume'],
    queryFn: () => getParentLeadVolumeReport().then(r => r.data),
  })

  if (isLoading) return <Spinner />
  if (isError || !data) {
    return (
      <div>
        <PageHeader title="Lead volume" />
        <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>Could not load the lead report.</p>
      </div>
    )
  }

  const current = PERIODS.find(p => p.key === period)!
  const rows: LeadVolumeBucket[] = [...data[period]].reverse()
  const max = Math.max(1, ...rows.map(r => r.total))
  const sum = (k: 'website_leads' | 'email_leads' | 'total') => rows.reduce((n, r) => n + r[k], 0)

  return (
    <div>
      <PageHeader title="Lead volume" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Website mobile-key enquiries and captured enquiry emails, in Melbourne time.
      </p>

      <div className="flex gap-2 mb-5 flex-wrap">
        {PERIODS.map(p => (
          <button
            key={p.key}
            type="button"
            onClick={() => setPeriod(p.key)}
            className="px-3 py-1.5 rounded-lg text-sm"
            style={{
              backgroundColor: p.key === period ? 'var(--ms-accent)' : 'var(--ms-surface)',
              color: p.key === period ? '#fff' : 'var(--ms-text)',
              border: '1px solid var(--ms-border)',
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-3 mb-6">
        {[
          ['Total leads', sum('total')],
          ['Website leads', sum('website_leads')],
          ['Email leads', sum('email_leads')],
        ].map(([label, value]) => (
          <Card key={label} className="p-5">
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>{label}</p>
            <p className="text-2xl font-semibold" style={{ color: 'var(--ms-text)' }}>{value}</p>
          </Card>
        ))}
      </div>

      <Card className="p-5 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ color: 'var(--ms-text-muted)' }}>
              <th className="text-left py-2 pr-4">{current.column}</th>
              <th className="text-right py-2 px-4">Website</th>
              <th className="text-right py-2 px-4">Email</th>
              <th className="text-right py-2 px-4">Total</th>
              <th className="py-2 pl-4 w-1/3" />
            </tr>
          </thead>
          <tbody style={{ color: 'var(--ms-text)' }}>
            {rows.map(r => (
              <tr key={r.period_start} style={{ borderTop: '1px solid var(--ms-border)' }}>
                <td className="py-2 pr-4">{formatPeriod(period, r.period_start)}</td>
                <td className="text-right py-2 px-4">{r.website_leads}</td>
                <td className="text-right py-2 px-4">{r.email_leads}</td>
                <td className="text-right py-2 px-4 font-semibold">{r.total}</td>
                <td className="py-2 pl-4">
                  <div className="h-2 rounded" style={{ width: `${(r.total / max) * 100}%`, backgroundColor: 'var(--ms-accent)' }} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
