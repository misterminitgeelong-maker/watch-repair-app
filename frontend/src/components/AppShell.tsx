import { useEffect, useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { Menu, WatchIcon, X } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import Sidebar from './Sidebar'
import { Button, Modal } from '@/components/ui'

const TUTORIAL_KEY = 'mainspring_tutorial_seen_v1'

export default function AppShell() {
  const { token, initializing, activeSiteTenantId, availableSites, switchSite } = useAuth()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const [showTutorial, setShowTutorial] = useState(false)
  const [switchingSite, setSwitchingSite] = useState(false)

  useEffect(() => {
    if (!token) return
    if (localStorage.getItem(TUTORIAL_KEY) === 'true') return
    setShowTutorial(true)
  }, [token])

  function dismissTutorial() {
    localStorage.setItem(TUTORIAL_KEY, 'true')
    setShowTutorial(false)
  }

  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)' }}>
        Preparing test session...
      </div>
    )
  }

  if (!token) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="h-screen md:flex" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <Sidebar className="hidden md:flex" />

      <div className="flex min-w-0 flex-1 flex-col">
        <header
          className="md:hidden sticky top-0 z-20 flex items-center justify-between px-4 py-3"
          style={{ backgroundColor: 'var(--cafe-surface)', borderBottom: '1px solid var(--cafe-border)' }}
        >
          <button
            onClick={() => setMobileNavOpen(true)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg"
            style={{ color: 'var(--cafe-text-mid)' }}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>

          <div className="flex items-center gap-2">
            <div
              className="h-7 w-7 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'var(--cafe-espresso-2)', color: 'var(--cafe-gold)' }}
            >
              <WatchIcon size={14} strokeWidth={2.5} />
            </div>
            <span style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }} className="text-base font-semibold">
              Mainspring
            </span>
          </div>

          <span className="w-9" />
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6 md:px-8 md:py-8">
          {availableSites.length > 1 && (
            <div className="mb-4 flex items-center justify-end gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: 'var(--cafe-text-muted)' }}>
                Active site
              </span>
              <select
                value={activeSiteTenantId ?? ''}
                disabled={switchingSite}
                onChange={async (e) => {
                  const nextTenantId = e.target.value
                  if (!nextTenantId || nextTenantId === activeSiteTenantId) return
                  setSwitchingSite(true)
                  try {
                    await switchSite(nextTenantId)
                  } finally {
                    setSwitchingSite(false)
                  }
                }}
                className="rounded-lg px-2.5 py-2 text-xs"
                style={{
                  backgroundColor: 'var(--cafe-surface)',
                  border: '1px solid var(--cafe-border-2)',
                  color: 'var(--cafe-text)',
                }}
              >
                {availableSites.map(site => (
                  <option key={site.tenant_id} value={site.tenant_id}>{site.tenant_name}</option>
                ))}
              </select>
            </div>
          )}
          <Outlet />
        </main>
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            className="absolute inset-0"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.35)' }}
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation overlay"
          />

          <div className="relative h-full w-[84vw] max-w-72">
            <Sidebar
              mobile
              className="h-full"
              onNavigate={() => setMobileNavOpen(false)}
              onClose={() => setMobileNavOpen(false)}
              closeIcon={<X size={18} />}
            />
          </div>
        </div>
      )}

      {showTutorial && (
        <Modal title="Quick Tour" onClose={dismissTutorial}>
          <div className="space-y-3 text-sm" style={{ color: 'var(--cafe-text-mid)' }}>
            <p style={{ color: 'var(--cafe-text)' }}>
              Welcome to Mainspring. Here is a quick guide to each section.
            </p>
            <p>
              Dashboard: live repair workload, open jobs, and status counts.
            </p>
            <p>
              Customers: customer history and linked repairs.
            </p>
            <p>
              Watch Repairs / Shoe Repairs: create jobs, quote work, and track progress.
            </p>
            <p>
              Invoices: payment tracking and printable invoices.
            </p>
            <p>
              Accounts: team access and roles.
            </p>
            <p>
              Reports / Database: export and operational visibility.
            </p>

            <div className="pt-1 flex gap-2">
              <Button variant="secondary" className="flex-1" onClick={dismissTutorial}>Skip</Button>
              <Button className="flex-1" onClick={dismissTutorial}>Start using app</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
