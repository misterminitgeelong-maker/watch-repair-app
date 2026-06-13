import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getApiErrorMessage, getAutoKeyJob, type AutoKeyJob, type Customer } from '@/lib/api'
import { Badge, Button, Modal, Spinner } from '@/components/ui'
import { formatCents } from './dispatchHelpers'

/**
 * Read-only job summary shown when a planner/scheduler card is opened.
 * Fetches the job by id; all display data comes from props + that fetch.
 */
export function PlannerJobDetailModal({
  jobId,
  onClose,
  customers,
  users,
}: {
  jobId: string
  onClose: () => void
  customers: Customer[]
  users: { id: string; full_name: string }[]
}) {
  const { data: job, isLoading, isError, error } = useQuery({
    queryKey: ['auto-key-jobs', jobId, 'planner-detail'],
    queryFn: () => getAutoKeyJob(jobId).then(r => r.data),
    enabled: !!jobId,
  })
  const customer = job ? customers.find(c => c.id === job.customer_id) : undefined
  const tech = job?.assigned_user_id ? users.find(u => u.id === job.assigned_user_id) : undefined
  const j = job as AutoKeyJob | undefined

  const row = (label: string, value: string | ReactNode) => (
    <>
      <dt className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }}>{label}</dt>
      <dd className="text-sm" style={{ color: 'var(--ms-text)' }}>{value}</dd>
    </>
  )

  return (
    <Modal title={j ? `Job #${j.job_number}` : 'Job details'} onClose={onClose}>
      {isLoading && <Spinner />}
      {isError && <p className="text-sm" style={{ color: '#C96A5A' }}>{getApiErrorMessage(error, 'Could not load job')}</p>}
      {j && (
        <div className="space-y-4">
          <p className="text-base font-medium" style={{ color: 'var(--ms-text)' }}>{j.title}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
            <dl className="contents">
              {row('Status', <Badge status={j.status} />)}
              {row('Customer', customer?.full_name ?? '—')}
              {row('Phone', customer?.phone ?? '—')}
              {row('Assigned tech', tech?.full_name ?? '—')}
              {row('Job type', j.job_type ?? '—')}
              {row('Vehicle', [j.vehicle_make, j.vehicle_model, j.vehicle_year, j.registration_plate].filter(Boolean).join(' · ') || '—')}
              {row('Address', j.job_address ?? '—')}
              {row('Scheduled', j.scheduled_at ? new Date(j.scheduled_at).toLocaleString() : '—')}
              {row('Priority', j.priority)}
              {row('Deposit', formatCents(j.deposit_cents))}
              {row('Cost / quote', formatCents(j.cost_cents))}
              {row('Key type', j.key_type ?? '—')}
              {row('Blade / chip', [j.blade_code, j.chip_type].filter(Boolean).join(' · ') || '—')}
            </dl>
          </div>
          {j.additional_services_json && (() => {
              try {
                const arr = JSON.parse(j.additional_services_json) as { preset?: string | null; custom?: string | null }[]
                if (!Array.isArray(arr) || arr.length === 0) return null
                const lines = arr.map(x => x.custom || x.preset).filter(Boolean)
                if (!lines.length) return null
                return (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--ms-text-muted)' }}>Additional services</p>
                    <ul className="text-sm list-disc pl-5 space-y-0.5" style={{ color: 'var(--ms-text)' }}>
                      {lines.map((t, i) => <li key={i}>{t}</li>)}
                    </ul>
                  </div>
                )
              } catch {
                return null
              }
            })()}
          {j.description && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--ms-text-muted)' }}>Description</p>
              <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--ms-text)' }}>{j.description}</p>
            </div>
          )}
          {j.tech_notes && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide mb-1" style={{ color: 'var(--ms-text-muted)' }}>Tech notes</p>
              <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--ms-text)' }}>{j.tech_notes}</p>
            </div>
          )}
          <div className="flex flex-wrap gap-2 pt-2">
            <Button variant="secondary" type="button" onClick={onClose}>Close</Button>
            <Link
              to={`/auto-key/${j.id}`}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium"
              style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
            >
              Open full job page
            </Link>
          </div>
        </div>
      )}
    </Modal>
  )
}
