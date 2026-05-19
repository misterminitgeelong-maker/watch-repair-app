import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { formatTenantLabel, getParentMobileJobsReport } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import { Card, Input, PageHeader, Spinner } from '@/components/ui'
import { defaultReportFromDate, defaultReportToDate, toIsoEnd, toIsoStart } from './dateRange'

export default function MinitMobileReportsPage() {
  const [fromYmd, setFromYmd] = useState(defaultReportFromDate)
  const [toYmd, setToYmd] = useState(defaultReportToDate)

  const { data, isLoading } = useQuery({
    queryKey: ['minit-mobile-jobs-report', fromYmd, toYmd],
    queryFn: () =>
      getParentMobileJobsReport({
        from_date: toIsoStart(fromYmd),
        to_date: toIsoEnd(toYmd),
        limit: 200,
      }).then(r => r.data),
  })

  return (
    <div>
      <PageHeader title="Mobile Services" />
      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)', marginTop: '-12px' }}>
        Network mobile jobs and operator activity — shop-referred and shop bookings.
      </p>

      <Card className="p-5 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <Input label="From" type="date" value={fromYmd} onChange={e => setFromYmd(e.target.value)} className="w-40" />
          <Input label="To" type="date" value={toYmd} onChange={e => setToYmd(e.target.value)} className="w-40" />
        </div>
      </Card>

      {isLoading || !data ? (
        <Spinner />
      ) : (
        <>
          <Card className="p-5 mb-6">
            <p className="text-sm font-semibold" style={{ color: 'var(--ms-text)' }}>
              {data.total_count} jobs in range · {data.active_count} still active
            </p>
          </Card>

          <Card className="overflow-hidden">
            {data.jobs.length === 0 ? (
              <p className="px-5 py-6 text-sm" style={{ color: 'var(--ms-text-muted)' }}>No mobile jobs in range.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--ms-border)', color: 'var(--ms-text-muted)' }}>
                      <th className="text-left px-5 py-2 font-medium">Job</th>
                      <th className="text-left px-5 py-2 font-medium">Operator</th>
                      <th className="text-left px-5 py-2 font-medium">Referring shop</th>
                      <th className="text-left px-5 py-2 font-medium">Status</th>
                      <th className="text-left px-5 py-2 font-medium">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.jobs.map(job => (
                      <tr key={job.id} style={{ borderBottom: '1px solid var(--ms-border)' }}>
                        <td className="px-5 py-2">
                          <span className="font-medium" style={{ color: 'var(--ms-text)' }}>{job.job_number}</span>
                          <span className="block text-xs" style={{ color: 'var(--ms-text-muted)' }}>{job.title}</span>
                        </td>
                        <td className="px-5 py-2">{formatTenantLabel(job.operator_name, job.operator_shop_number)}</td>
                        <td className="px-5 py-2">
                          {job.referring_shop_name
                            ? formatTenantLabel(job.referring_shop_name, job.referring_shop_number)
                            : '—'}
                        </td>
                        <td className="px-5 py-2 capitalize">{job.status.replace(/_/g, ' ')}</td>
                        <td className="px-5 py-2 whitespace-nowrap">{formatDate(job.created_at)}</td>
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
