import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { MapPin, Radio } from 'lucide-react'
import { claimPoolJob, getApiErrorMessage, listJobPool, type IntakePoolJob } from '@/lib/api'
import { Card, PageHeader, Button, Spinner, EmptyState } from '@/components/ui'
import { formatDate } from '@/lib/utils'

const RING_COLORS: Record<number, { bg: string; text: string }> = {
  1: { bg: 'var(--ms-badge-done-bg)', text: 'var(--ms-badge-done-text)' },
  2: { bg: 'var(--ms-badge-in-bg)', text: 'var(--ms-badge-in-text)' },
  3: { bg: 'var(--ms-badge-wait-bg)', text: 'var(--ms-badge-wait-text)' },
}
function ringStyle(ring: number) {
  return RING_COLORS[ring] ?? { bg: 'var(--ms-badge-neutral-bg)', text: 'var(--ms-badge-neutral-text)' }
}

function RingBadge({ ring }: { ring: number }) {
  const s = ringStyle(ring)
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold"
      style={{ backgroundColor: s.bg, color: s.text }}
    >
      <Radio size={10} />
      Ring {ring}
    </span>
  )
}

function JobCard({ job, onClaim }: { job: IntakePoolJob; onClaim: (id: string) => void }) {
  const [confirming, setConfirming] = useState(false)
  return (
    <div className="p-4 rounded-lg border space-y-2" style={{ borderColor: 'var(--ms-border)', backgroundColor: 'var(--ms-surface)' }}>
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-0.5 flex-1">
          <p className="font-semibold text-sm" style={{ color: 'var(--ms-text)' }}>{job.customer_name}</p>
          {(job.vehicle_make || job.vehicle_model) && (
            <p className="text-xs" style={{ color: 'var(--ms-text-mid)' }}>
              {[job.vehicle_make, job.vehicle_model, job.vehicle_year].filter(Boolean).join(' ')}
              {job.registration_plate && ` · ${job.registration_plate}`}
            </p>
          )}
        </div>
        <RingBadge ring={job.ring} />
      </div>

      <div className="flex items-start gap-1.5 text-xs" style={{ color: 'var(--ms-text-mid)' }}>
        <MapPin size={12} className="mt-0.5 shrink-0" />
        <span>{job.job_address}</span>
      </div>

      {job.description && (
        <p className="text-xs line-clamp-2" style={{ color: 'var(--ms-text-muted)' }}>{job.description}</p>
      )}

      <div className="flex items-center justify-between pt-1">
        <span className="text-xs" style={{ color: 'var(--ms-text-muted)' }}>Posted {formatDate(job.created_at)}</span>
        {confirming ? (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setConfirming(false)}>Cancel</Button>
            <Button onClick={() => onClaim(job.id)}>Confirm claim</Button>
          </div>
        ) : (
          <Button onClick={() => setConfirming(true)}>Claim job</Button>
        )}
      </div>
    </div>
  )
}

export default function JobPoolPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [error, setError] = useState('')

  const poolQuery = useQuery({
    queryKey: ['job-pool'],
    queryFn: () => listJobPool().then(r => r.data),
    refetchInterval: 30_000,
  })

  const claimMut = useMutation({
    mutationFn: (id: string) => claimPoolJob(id).then(r => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['job-pool'] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      navigate(`/auto-key/${data.auto_key_job_id}`)
    },
    onError: (err) => setError(getApiErrorMessage(err)),
  })

  const jobs = poolQuery.data ?? []
  const ring1 = jobs.filter(j => j.ring === 1)
  const ring2 = jobs.filter(j => j.ring === 2)
  const ring3plus = jobs.filter(j => j.ring >= 3)

  return (
    <div>
      <PageHeader title="Dispatch Pool" />

      <p className="text-sm mb-5" style={{ color: 'var(--ms-text-muted)' }}>
        Unclaimed jobs near your base location. Ring 1 is closest — claim a job to create it in your job board.
      </p>

      {poolQuery.error && (
        <p className="text-sm mb-3" style={{ color: 'var(--ms-error)' }}>{getApiErrorMessage(poolQuery.error)}</p>
      )}
      {error && (
        <p className="text-sm mb-3" style={{ color: 'var(--ms-error)' }}>{error}</p>
      )}

      {poolQuery.isLoading ? <Spinner /> : jobs.length === 0 ? (
        <Card><EmptyState message="No unclaimed jobs in your service area." /></Card>
      ) : (
        <div className="space-y-6">
          {ring1.length > 0 && (
            <section>
              <h2 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                Ring 1 — Priority
              </h2>
              <div className="space-y-3">
                {ring1.map(j => <JobCard key={j.id} job={j} onClaim={(id) => claimMut.mutate(id)} />)}
              </div>
            </section>
          )}
          {ring2.length > 0 && (
            <section>
              <h2 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                Ring 2
              </h2>
              <div className="space-y-3">
                {ring2.map(j => <JobCard key={j.id} job={j} onClaim={(id) => claimMut.mutate(id)} />)}
              </div>
            </section>
          )}
          {ring3plus.length > 0 && (
            <section>
              <h2 className="text-xs font-bold tracking-widest uppercase mb-3" style={{ color: 'var(--ms-text-muted)' }}>
                Ring 3+
              </h2>
              <div className="space-y-3">
                {ring3plus.map(j => <JobCard key={j.id} job={j} onClaim={(id) => claimMut.mutate(id)} />)}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  )
}
