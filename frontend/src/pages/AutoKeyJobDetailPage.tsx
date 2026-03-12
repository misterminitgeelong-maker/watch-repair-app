import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import {
  getAutoKeyJob,
  getApiErrorMessage,
  listAutoKeyInvoices,
  listAutoKeyQuotes,
  listCustomerAccounts,
  updateAutoKeyJob,
  updateAutoKeyJobStatus,
  type CustomerAccount,
  type JobStatus,
} from '@/lib/api'
import { Badge, Card, EmptyState, PageHeader, Select, Spinner } from '@/components/ui'
import { formatDate } from '@/lib/utils'

const STATUSES: JobStatus[] = [
  'awaiting_quote',
  'awaiting_go_ahead',
  'go_ahead',
  'working_on',
  'awaiting_parts',
  'completed',
  'awaiting_collection',
  'collected',
  'no_go',
]

function formatCents(value: number) {
  return `$${(value / 100).toFixed(2)}`
}

export default function AutoKeyJobDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [error, setError] = useState('')

  const { data: job, isLoading } = useQuery({
    queryKey: ['auto-key-job', id],
    queryFn: () => getAutoKeyJob(id!).then(r => r.data),
    enabled: !!id,
  })

  const { data: customerAccounts = [] } = useQuery({
    queryKey: ['customer-accounts'],
    queryFn: () => listCustomerAccounts().then(r => r.data),
  })

  const { data: quotes = [] } = useQuery({
    queryKey: ['auto-key-quotes', id],
    queryFn: () => listAutoKeyQuotes(id!).then(r => r.data),
    enabled: !!id,
  })

  const { data: invoices = [] } = useQuery({
    queryKey: ['auto-key-invoices', id],
    queryFn: () => listAutoKeyInvoices(id!).then(r => r.data),
    enabled: !!id,
  })

  const statusMut = useMutation({
    mutationFn: (status: JobStatus) => updateAutoKeyJobStatus(id!, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to update status.')),
  })

  const accountMut = useMutation({
    mutationFn: (customer_account_id: string | null) => updateAutoKeyJob(id!, { customer_account_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auto-key-job', id] })
      qc.invalidateQueries({ queryKey: ['auto-key-jobs'] })
      setError('')
    },
    onError: err => setError(getApiErrorMessage(err, 'Failed to update customer account.')),
  })

  if (isLoading) return <Spinner />
  if (!job) return <EmptyState message='Auto key job not found.' />

  const matchingAccounts = customerAccounts.filter((a: CustomerAccount) => a.customer_ids.includes(job.customer_id))

  return (
    <div>
      <div className='mb-5'>
        <Link
          to='/auto-key'
          className='inline-flex items-center gap-1 text-sm font-medium transition-colors'
          style={{ color: 'var(--cafe-text-muted)' }}
        >
          <ChevronLeft size={14} /> Back to Auto Key Jobs
        </Link>
      </div>

      <PageHeader title={`#${job.job_number} · ${job.title}`} />

      <div className='grid grid-cols-1 lg:grid-cols-3 gap-5'>
        <Card className='p-5 space-y-3'>
          <h2 className='font-semibold text-xs uppercase tracking-widest' style={{ color: 'var(--cafe-text-muted)' }}>Job Info</h2>
          <div className='space-y-2 text-sm'>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Status</span><Badge status={job.status} /></div>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Priority</span><span className='capitalize'>{job.priority}</span></div>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Created</span><span>{formatDate(job.created_at)}</span></div>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Vehicle</span><span>{job.vehicle_make || 'Unknown'} {job.vehicle_model || ''}</span></div>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Programming</span><span>{job.programming_status.replace(/_/g, ' ')}</span></div>
            <div className='flex justify-between'><span style={{ color: 'var(--cafe-text-muted)' }}>Qty</span><span>{job.key_quantity}</span></div>
          </div>

          <Select
            label='Status'
            value={job.status}
            onChange={e => statusMut.mutate(e.target.value as JobStatus)}
            disabled={statusMut.isPending}
          >
            {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
          </Select>

          <Select
            label='Customer Account'
            value={job.customer_account_id ?? ''}
            onChange={e => accountMut.mutate(e.target.value || null)}
            disabled={accountMut.isPending}
          >
            <option value=''>No B2B account</option>
            {matchingAccounts.map((account: CustomerAccount) => (
              <option key={account.id} value={account.id}>{account.name}{account.account_code ? ` (${account.account_code})` : ''}</option>
            ))}
          </Select>

          {error && <p className='text-sm' style={{ color: '#C96A5A' }}>{error}</p>}
        </Card>

        <div className='lg:col-span-2 space-y-5'>
          <Card>
            <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>Quotes</h2>
            </div>
            {(quotes ?? []).length === 0 ? (
              <p className='px-5 py-4 text-sm' style={{ color: 'var(--cafe-text-muted)' }}>No quotes yet.</p>
            ) : (
              quotes.map(q => (
                <div key={q.id} className='px-5 py-3 text-sm flex items-center justify-between' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  <div>
                    <p style={{ color: 'var(--cafe-text)' }}>{formatDate(q.created_at)}</p>
                    <p className='text-xs capitalize' style={{ color: 'var(--cafe-text-muted)' }}>{q.status}</p>
                  </div>
                  <p className='font-semibold' style={{ color: 'var(--cafe-text)' }}>{formatCents(q.total_cents)}</p>
                </div>
              ))
            )}
          </Card>

          <Card>
            <div className='px-5 py-3.5' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
              <h2 className='font-semibold' style={{ color: 'var(--cafe-text)' }}>Invoices</h2>
            </div>
            {(invoices ?? []).length === 0 ? (
              <p className='px-5 py-4 text-sm' style={{ color: 'var(--cafe-text-muted)' }}>No invoices yet.</p>
            ) : (
              invoices.map(inv => (
                <div key={inv.id} className='px-5 py-3 text-sm flex items-center justify-between' style={{ borderBottom: '1px solid var(--cafe-border)' }}>
                  <div>
                    <p style={{ color: 'var(--cafe-text)' }}>{inv.invoice_number}</p>
                    <p className='text-xs capitalize' style={{ color: 'var(--cafe-text-muted)' }}>{inv.status} · {formatDate(inv.created_at)}</p>
                  </div>
                  <p className='font-semibold' style={{ color: 'var(--cafe-text)' }}>{formatCents(inv.total_cents)}</p>
                </div>
              ))
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
