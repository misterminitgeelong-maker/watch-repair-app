import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { Card, PageHeader, Spinner } from '@/components/ui'
import { getApiErrorMessage, getHqShoeSummary, searchHqShoeJobs } from '@/lib/api'
import { formatCents } from '@/lib/money'
import { STATUS_LABELS } from '@/lib/utils'

const days = (value: number | null) => (value == null ? '–' : `${value}d`)

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="p-4">
      <p className="text-xs uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>{label}</p>
      <p className="text-2xl font-semibold mt-1" style={{ color: 'var(--ms-text)' }}>{value}</p>
    </Card>
  )
}

/** Every shoe repair across the HQ's shops: where they are, how long they take, and a network-wide search. */
export default function HqShoeRepairsPage() {
  const summary = useQuery({ queryKey: ['hq-shoe-summary'], queryFn: () => getHqShoeSummary().then(r => r.data) })
  const [term, setTerm] = useState('')
  const [submitted, setSubmitted] = useState('')
  const search = useQuery({
    queryKey: ['hq-shoe-search', submitted],
    queryFn: () => searchHqShoeJobs({ q: submitted, limit: 50 }).then(r => r.data),
  })

  return (
    <div className="p-4 sm:p-6 space-y-6">
      <PageHeader title="Shoe repairs" />
      {summary.isLoading && <Spinner />}
      {summary.isError && <p role="alert" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(summary.error, 'Could not load shoe repairs.')}</p>}
      {summary.data && (
        <>
          <div className="grid gap-3 grid-cols-2 lg:grid-cols-6">
            <Stat label="Shops" value={summary.data.totals.shops} />
            <Stat label="Opened" value={summary.data.totals.opened} />
            <Stat label="In progress" value={summary.data.totals.active} />
            <Stat label="Ready to collect" value={summary.data.totals.ready_to_collect} />
            <Stat label="Billed" value={formatCents(summary.data.totals.billed_cents)} />
            <Stat label="Avg turnaround" value={days(summary.data.totals.avg_turnaround_days)} />
          </div>
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left" style={{ color: 'var(--ms-text-muted)' }}>
                  <th className="p-3">Shop</th><th className="p-3">Region</th><th className="p-3">Opened</th><th className="p-3">In progress</th>
                  <th className="p-3">Ready</th><th className="p-3">Collected</th><th className="p-3">Billed</th><th className="p-3">Avg turnaround</th><th className="p-3">Oldest open</th>
                </tr>
              </thead>
              <tbody>
                {summary.data.by_shop.map(row => (
                  <tr key={row.tenant_id} className="border-t" style={{ borderColor: 'var(--ms-border)' }}>
                    <td className="p-3 font-medium">{row.tenant_name}</td><td className="p-3">{row.region ?? '–'}</td>
                    <td className="p-3">{row.opened}</td><td className="p-3">{row.active}</td><td className="p-3">{row.ready_to_collect}</td>
                    <td className="p-3">{row.collected}</td><td className="p-3">{formatCents(row.billed_cents)}</td>
                    <td className="p-3">{days(row.avg_turnaround_days)}</td><td className="p-3">{days(row.oldest_active_days)}</td>
                  </tr>
                ))}
                {!summary.data.by_shop.length && <tr><td className="p-4" colSpan={9}>No shops are linked to this HQ yet.</td></tr>}
              </tbody>
            </table>
          </Card>
        </>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Find a repair</h2>
        <form className="flex gap-2" onSubmit={e => { e.preventDefault(); setSubmitted(term.trim()) }}>
          <label className="sr-only" htmlFor="hq-shoe-search">Ticket number, customer name or phone</label>
          <input id="hq-shoe-search" className="flex-1 border rounded p-2" placeholder="Ticket number, customer name or phone" value={term} onChange={e => setTerm(e.target.value)} />
          <button className="console-button primary inline-flex items-center gap-2" type="submit"><Search size={14} />Search</button>
        </form>
        {search.isLoading && <Spinner />}
        {search.isError && <p role="alert" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(search.error, 'Search failed.')}</p>}
        {search.data && (
          <Card className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left" style={{ color: 'var(--ms-text-muted)' }}>
                <th className="p-3">Ticket</th><th className="p-3">Shop</th><th className="p-3">Customer</th><th className="p-3">Shoe</th><th className="p-3">Repair</th><th className="p-3">Status</th><th className="p-3">Age</th>
              </tr></thead>
              <tbody>
                {search.data.jobs.map(job => (
                  <tr key={job.id} className="border-t" style={{ borderColor: 'var(--ms-border)' }}>
                    <td className="p-3 font-medium">{job.job_number}</td><td className="p-3">{job.tenant_name}</td><td className="p-3">{job.customer_name}</td>
                    <td className="p-3">{job.shoe ?? '–'}</td><td className="p-3">{job.title}</td>
                    <td className="p-3">{STATUS_LABELS[job.status] ?? job.status.replace(/_/g, ' ')}</td><td className="p-3">{job.age_days}d</td>
                  </tr>
                ))}
                {!search.data.jobs.length && <tr><td className="p-4" colSpan={7}>No repairs found.</td></tr>}
              </tbody>
            </table>
            {search.data.has_more && <p className="p-3 text-xs" style={{ color: 'var(--ms-text-muted)' }}>Showing the first 50. Narrow the search to see more.</p>}
          </Card>
        )}
      </section>
    </div>
  )
}
