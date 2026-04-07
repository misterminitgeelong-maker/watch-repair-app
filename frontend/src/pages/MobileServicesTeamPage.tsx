import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { UserPlus } from 'lucide-react'
import { listUsers, type TenantUser } from '@/lib/api'
import { useAuth } from '@/context/AuthContext'
import MobileServicesSubNav from '@/components/MobileServicesSubNav'
import { AddTechnicianModal, MobileCommissionRulesModal } from '@/components/MobileServicesTechnicianModals'
import { Button, Card, EmptyState, PageHeader, Spinner } from '@/components/ui'

function commissionEnabled(json: string | null | undefined): boolean {
  if (!json?.trim()) return false
  try {
    const r = JSON.parse(json) as { enabled?: boolean }
    return Boolean(r.enabled)
  } catch {
    return false
  }
}

export default function MobileServicesTeamPage() {
  const { role } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [showAddTech, setShowAddTech] = useState(false)
  const [showCommissionRules, setShowCommissionRules] = useState(false)
  const [addedBanner, setAddedBanner] = useState(false)

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => listUsers().then(r => r.data),
  })

  const techs: TenantUser[] = users.filter(u => u.role === 'tech')

  useEffect(() => {
    const st = location.state as { addedTech?: boolean } | null
    if (st?.addedTech) {
      setAddedBanner(true)
      navigate(location.pathname, { replace: true, state: {} })
    }
  }, [location.pathname, location.state, navigate])

  return (
    <div className="p-6">
      <MobileServicesSubNav className="mb-4" />
      <PageHeader
        title="Team"
        action={(
          <div className="flex flex-wrap items-center gap-2">
            {role === 'owner' && (
              <Button variant="secondary" onClick={() => setShowAddTech(true)} type="button">
                <UserPlus size={16} />Add technician
              </Button>
            )}
            {(role === 'owner' || role === 'manager') && (
              <Button variant="secondary" onClick={() => setShowCommissionRules(true)} type="button">
                Commission rules
              </Button>
            )}
          </div>
        )}
      />
      <p className="text-sm -mt-4 mb-6" style={{ color: 'var(--cafe-text-muted)' }}>
        Technicians you can assign to mobile jobs.
      </p>

      {addedBanner && (
        <div
          className="mb-4 rounded-xl border px-4 py-3 text-sm"
          style={{ borderColor: 'var(--cafe-border-2)', backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text)' }}
        >
          Technician added. They appear in the list below and in job assignment menus.
          <button
            type="button"
            className="ml-2 underline font-medium"
            style={{ color: 'var(--cafe-amber)' }}
            onClick={() => setAddedBanner(false)}
          >
            Dismiss
          </button>
        </div>
      )}

      {isLoading && <Spinner />}
      {!isLoading && techs.length === 0 && (
        <Card className="p-6">
          <EmptyState
            message={role === 'owner'
              ? 'No technicians yet — add one to give them a login and assign them on the dispatch board.'
              : 'No technicians yet. Ask an owner to add accounts; they will appear here.'}
          />
          {role === 'owner' && (
            <div className="mt-4 flex justify-center">
              <Button type="button" onClick={() => setShowAddTech(true)}>
                <UserPlus size={16} />Add technician
              </Button>
            </div>
          )}
        </Card>
      )}
      {!isLoading && techs.length > 0 && (
        <Card className="overflow-hidden">
          {/* Mobile card list */}
          <div className="md:hidden divide-y" style={{ borderColor: 'var(--cafe-border-2)' }}>
            {techs.map(t => (
              <div key={t.id} className="p-4 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium" style={{ color: 'var(--cafe-text)' }}>{t.full_name}</p>
                  {t.is_active
                    ? <span className="text-xs font-medium px-2 py-0.5 rounded" style={{ backgroundColor: 'rgba(90,140,90,0.15)', color: '#5a8c5a' }}>Active</span>
                    : <span className="text-xs font-medium px-2 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}>Inactive</span>}
                </div>
                <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>{t.email}</p>
                <p className="text-xs" style={{ color: 'var(--cafe-text-muted)' }}>
                  Commission:{' '}
                  {commissionEnabled(t.mobile_commission_rules_json)
                    ? <span className="font-medium" style={{ color: '#1F5C24' }}>On</span>
                    : <span>Off</span>}
                </p>
              </div>
            ))}
          </div>
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--cafe-border-2)', backgroundColor: 'var(--cafe-bg)' }}>
                  <th className="text-left font-semibold px-4 py-3" style={{ color: 'var(--cafe-text-muted)' }}>Name</th>
                  <th className="text-left font-semibold px-4 py-3" style={{ color: 'var(--cafe-text-muted)' }}>Email</th>
                  <th className="text-left font-semibold px-4 py-3" style={{ color: 'var(--cafe-text-muted)' }}>Status</th>
                  <th className="text-left font-semibold px-4 py-3" style={{ color: 'var(--cafe-text-muted)' }}>Commission</th>
                </tr>
              </thead>
              <tbody>
                {techs.map(t => (
                  <tr key={t.id} style={{ borderBottom: '1px solid var(--cafe-border-2)' }}>
                    <td className="px-4 py-3 font-medium" style={{ color: 'var(--cafe-text)' }}>{t.full_name}</td>
                    <td className="px-4 py-3" style={{ color: 'var(--cafe-text-muted)' }}>{t.email}</td>
                    <td className="px-4 py-3">
                      {t.is_active
                        ? <span className="text-xs font-medium px-2 py-0.5 rounded" style={{ backgroundColor: 'rgba(90,140,90,0.15)', color: '#5a8c5a' }}>Active</span>
                        : <span className="text-xs font-medium px-2 py-0.5 rounded" style={{ backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }}>Inactive</span>}
                    </td>
                    <td className="px-4 py-3">
                      {commissionEnabled(t.mobile_commission_rules_json)
                        ? <span className="font-medium" style={{ color: '#1F5C24' }}>On</span>
                        : <span style={{ color: 'var(--cafe-text-muted)' }}>Off</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs px-4 py-3 border-t" style={{ borderColor: 'var(--cafe-border-2)', color: 'var(--cafe-text-muted)' }}>
            To change passwords, roles, or deactivate logins, use{' '}
            <Link to="/accounts" className="underline font-medium" style={{ color: 'var(--cafe-amber)' }}>Team accounts</Link>.
          </p>
        </Card>
      )}

      {showAddTech && (
        <AddTechnicianModal
          onClose={() => setShowAddTech(false)}
          onAdded={() => setAddedBanner(true)}
        />
      )}
      {showCommissionRules && (
        <MobileCommissionRulesModal onClose={() => setShowCommissionRules(false)} />
      )}
    </div>
  )
}
