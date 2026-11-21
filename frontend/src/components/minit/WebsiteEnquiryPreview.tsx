import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { Button } from '@/components/ui'
import { LoadError } from './LoadError'

interface Enquiry {
  name: string; phone: string | null; email: string | null; suburb: string | null
  state: string | null; notes: string | null; status: string
}

export default function WebsiteEnquiryPreview({ id }: { id: string }) {
  const [open, setOpen] = useState(false)
  const query = useQuery({ queryKey: ['support-office-website-enquiry', id], enabled: open,
    queryFn: () => api.get<Enquiry>(`/parent-accounts/me/website-enquiries/${id}`).then(r => r.data) })
  return <div className="mt-3 text-sm">
    <Button variant="secondary" onClick={() => setOpen(!open)}>{open ? 'Hide enquiry' : 'View enquiry'}</Button>
    {open && <>
      {query.isPending && <p role="status">Loading enquiry…</p>}
      {query.isError && <LoadError error={query.error} message="Could not load this enquiry." onRetry={() => void query.refetch()} />}
      {query.data && <dl className="mt-2 space-y-1">
        <dt>Customer</dt><dd>{query.data.name}</dd>
        <dt>Contact</dt><dd>{[query.data.phone, query.data.email].filter(Boolean).join(' · ') || 'Not supplied'}</dd>
        <dt>Location</dt><dd>{[query.data.suburb, query.data.state].filter(Boolean).join(', ')}</dd>
        <dt>Details</dt><dd className="whitespace-pre-wrap">{query.data.notes || 'No additional details'}</dd>
        <dt>Status</dt><dd>{query.data.status}</dd>
      </dl>}
    </>}
  </div>
}
