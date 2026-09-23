import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/context/AuthContext'
import {
  acceptNetworkLinkRequest,
  declineNetworkLinkRequest,
  getApiErrorMessage,
  listNetworkLinkRequests,
  type NetworkLinkRequest,
} from '@/lib/api'
import { useToast } from '@/lib/toast'

const QUERY_KEY = ['network-link-requests'] as const

/**
 * A network asking to add this shop. Linking lets that network's HQ open the
 * shop with owner rights, so it only happens when the owner says yes here.
 */
export default function NetworkLinkRequestsBanner() {
  const { role } = useAuth()
  const qc = useQueryClient()
  const toast = useToast()
  const isOwner = role === 'owner'

  const { data } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => listNetworkLinkRequests().then(r => r.data),
    enabled: isOwner,
    staleTime: 60_000,
  })

  const decide = useMutation({
    mutationFn: ({ request, accept }: { request: NetworkLinkRequest; accept: boolean }) =>
      (accept ? acceptNetworkLinkRequest(request.id) : declineNetworkLinkRequest(request.id)).then(r => r.data),
    onSuccess: result => {
      toast.success(
        result.status === 'accepted'
          ? `Your shop is now part of ${result.parent_account_name}.`
          : `Declined ${result.parent_account_name}'s request.`,
      )
      void qc.invalidateQueries({ queryKey: QUERY_KEY })
    },
    onError: err => toast.error(getApiErrorMessage(err, 'Could not answer the request.')),
  })

  if (!isOwner || !data?.length) return null

  return (
    <div className="print-hide mb-4 space-y-2">
      {data.map(request => (
        <div
          key={request.id}
          role="region"
          aria-label="Network request"
          className="rounded-xl px-4 py-3 text-sm"
          style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
        >
          <p className="font-semibold">{request.parent_account_name} wants to add your shop to its network</p>
          <p className="mt-1" style={{ color: 'var(--ms-text-muted)' }}>
            If you accept, their head office can see this shop and open it with owner access
            {request.requested_by_email ? ` (requested by ${request.requested_by_email})` : ''}. Only accept if you
            recognise them.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className="min-h-11 rounded-lg px-4 text-sm font-semibold text-white"
              style={{ backgroundColor: 'var(--ms-accent)' }}
              disabled={decide.isPending}
              onClick={() => decide.mutate({ request, accept: true })}
            >
              Accept
            </button>
            <button
              type="button"
              className="min-h-11 rounded-lg px-4 text-sm font-semibold"
              style={{ border: '1px solid var(--ms-border)', color: 'var(--ms-text)' }}
              disabled={decide.isPending}
              onClick={() => decide.mutate({ request, accept: false })}
            >
              Decline
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
