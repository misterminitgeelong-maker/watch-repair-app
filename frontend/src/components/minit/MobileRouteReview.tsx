import { useQuery } from '@tanstack/react-query'
import api from '@/lib/api'
import { Button, Card } from '@/components/ui'
import { LoadError } from './LoadError'

interface RouteReview {
  testing_mode: boolean
  testing_inbox: { tenant_id: string; name: string } | null
  escalation_configured: boolean
  total_routes: number
  targets: { tenant_id: string; name: string; slug: string | null; route_count: number
    states: string[]; issues: string[]; sample_suburbs: string[] }[]
}

export default function MobileRouteReview() {
  const query = useQuery({ queryKey: ['mobile-route-review'],
    queryFn: () => api.get<RouteReview>('/parent-accounts/me/mobile-lead-routes/review').then(r => r.data) })
  const data = query.data
  return <Card className="mt-6 p-5 space-y-3">
    <h2 className="font-semibold">Territory readiness review</h2>
    <p className="text-sm">Read-only check. Review the exact real operator before proposing any reassignment. Matching shop numbers alone do not establish ownership.</p>
    <Button variant="secondary" disabled={query.isFetching} onClick={() => void query.refetch()}>Refresh review</Button>
    {query.isPending && <p role="status">Loading route review…</p>}
    {query.isError && <LoadError error={query.error} message="Could not review territory routes." onRetry={() => void query.refetch()} />}
    {data && <>
      <p className="text-sm">Testing mode: <strong>{data.testing_mode ? 'ON' : 'OFF'}</strong>. Testing Inbox: {data.testing_inbox?.name ?? 'No unique active Support office site — investigate before testing intake'}.</p>
      <p className="text-sm">Separate production escalation: {data.escalation_configured ? 'configured' : 'not configured'}. Testing mode uses the Support office Inbox and sends no SMS or email alerts.</p>
      <p className="text-sm">{data.total_routes.toLocaleString()} mapped suburbs. Readiness below describes accounts; testing mode still bypasses operator dispatch.</p>
      <div className="overflow-x-auto"><table className="w-full text-sm text-left">
        <thead><tr><th className="p-2">Current account</th><th className="p-2">Suburbs</th><th className="p-2">Review</th></tr></thead>
        <tbody>{data.targets.map(t => <tr key={t.tenant_id}>
          <td className="p-2">{t.name}<div className="text-xs">{t.slug} · {t.states.join(', ')}</div></td>
          <td className="p-2">{t.route_count}<div className="text-xs">Examples: {t.sample_suburbs.join(', ')}</div></td>
          <td className="p-2">{t.issues.length ? t.issues.map(issue => <p key={issue}>{issue}</p>) : 'No readiness issues found by this check'}<p className="text-xs">Replacement: requires a separately reviewed exact account.</p></td>
        </tr>)}</tbody>
      </table></div>
    </>}
  </Card>
}
