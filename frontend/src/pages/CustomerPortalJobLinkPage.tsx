import { useEffect } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { openPortalFromJobLink } from '@/lib/api'
import { PortalLoading } from '@/components/portal/PortalChrome'

/**
 * The link in booking and status texts/emails. It trades the job's own token for
 * a customer portal session, so the customer lands in My Repairs with no sign-in.
 * If that fails (old link, offline), fall back to the job's own page.
 */
export default function CustomerPortalJobLinkPage() {
  const { jobType = '', statusToken = '' } = useParams<{ jobType: string; statusToken: string }>()
  const navigate = useNavigate()
  const { data, isError } = useQuery({
    queryKey: ['portal-job-link', jobType, statusToken],
    queryFn: () => openPortalFromJobLink(jobType, statusToken).then((r) => r.data),
    retry: false,
    staleTime: Infinity,
  })

  useEffect(() => {
    if (data) {
      navigate(`/customer-portal/s/${data.session_token}?job=${encodeURIComponent(data.job_number)}`, { replace: true })
    }
  }, [data, navigate])

  if (isError) return <Navigate to={`/customer-portal/job/${jobType}/${statusToken}`} replace />
  return <PortalLoading label="Opening your repairs…" />
}
