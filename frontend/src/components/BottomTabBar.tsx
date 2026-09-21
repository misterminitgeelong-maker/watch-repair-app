import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Inbox,
  Wrench,
  Scissors,
  KeyRound,
  MoreHorizontal,
  Users,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { isDemoModeEnabled } from '@/lib/onboarding'
import { cn } from '@/lib/utils'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart3,
  Receipt,
  ClipboardList,
  Database,
  UserCog,
  Building2,
  Sparkles,
  LogOut,
} from 'lucide-react'
import ChangelogModal from './ChangelogModal'
import { useInboxCount } from '@/hooks/useInboxCount'

/**
 * Mobile bottom tab bar — only shown on screens < md (768px).
 * Tabs are driven by feature flags so subscribers only see what they pay for.
 */
type TabItem = { to: string; label: string; icon: typeof Wrench }

function pickServiceTabs(hasWatch: boolean, hasShoe: boolean, hasMobile: boolean): {
  primary: TabItem[]
  overflow: TabItem[]
} {
  const watchTab: TabItem = { to: '/jobs', label: 'Watch', icon: Wrench }
  const shoeTab: TabItem = { to: '/shoe-repairs', label: 'Shoe', icon: Scissors }
  const mobileTab: TabItem = { to: '/auto-key', label: 'Mobile', icon: KeyRound }

  if (hasMobile) {
    if (hasWatch && hasShoe) return { primary: [watchTab, mobileTab], overflow: [shoeTab] }
    if (hasWatch) return { primary: [watchTab, mobileTab], overflow: [] }
    if (hasShoe) return { primary: [shoeTab, mobileTab], overflow: [] }
    return { primary: [mobileTab], overflow: [] }
  }

  const others = [hasWatch && watchTab, hasShoe && shoeTab].filter(Boolean) as TabItem[]
  if (others.length === 0) {
    return { primary: [{ to: '/customers', label: 'Customers', icon: Users }], overflow: [] }
  }
  return { primary: others.slice(0, 2), overflow: others.slice(2) }
}

export default function BottomTabBar() {
  const { hasFeature, logout, availableSites, activeSiteTenantId, switchSite } = useAuth()
  const demoModeEnabled = isDemoModeEnabled()
  const navigate = useNavigate()
  const [showMore, setShowMore] = useState(false)
  const [showChangelog, setShowChangelog] = useState(false)
  const [switchingSite, setSwitchingSite] = useState(false)
  const inboxCount = useInboxCount()

  const hasWatch = hasFeature('watch')
  const hasShoe = hasFeature('shoe')
  const hasMobile = hasFeature('auto_key')

  const { primary: primaryServiceTabs, overflow: overflowServiceTabs } = pickServiceTabs(hasWatch, hasShoe, hasMobile)

  const moreMenuItems = [
    ...overflowServiceTabs,
    { to: '/customers', label: 'Customers', icon: Users },
    { to: '/invoices', label: 'Invoices', icon: Receipt },
    { to: '/reports', label: 'Reports', icon: BarChart3 },
    !demoModeEnabled && { to: '/stocktakes', label: 'Stocktake', icon: ClipboardList },
    !demoModeEnabled && hasFeature('customer_accounts') && { to: '/customer-accounts', label: 'Accounts', icon: Building2 },
    !demoModeEnabled && hasFeature('multi_site') && { to: '/parent-account', label: 'Parent', icon: Building2 },
    !demoModeEnabled && { to: '/database', label: 'Database', icon: Database },
    { to: '/accounts', label: 'Settings', icon: UserCog },
  ].filter(Boolean) as TabItem[]

  const tabStyle = (isActive: boolean) => ({
    color: isActive ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
  })

  return (
    <>
      {/* More menu overlay */}
      {showMore && (
        <div
          className="fixed inset-x-0 top-0 z-40 md:hidden"
          style={{ bottom: 'var(--ms-mobile-bar-h)' }}
          onClick={() => setShowMore(false)}
        >
          <div className="absolute inset-0" style={{ backgroundColor: 'rgba(0,0,0,0.3)' }} />
          <div
            className="absolute bottom-2 left-0 right-0 mx-3 rounded-2xl overflow-hidden shadow-2xl"
            style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
            onClick={(e) => e.stopPropagation()}
          >
            {availableSites.length > 1 && !demoModeEnabled && (
              <div className="px-3 py-3" style={{ borderBottom: '1px solid var(--ms-border)' }}>
                <label className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wide" style={{ color: 'var(--ms-text-muted)' }} htmlFor="mobile-active-site">
                  Active site
                </label>
                <select
                  id="mobile-active-site"
                  value={activeSiteTenantId ?? ''}
                  disabled={switchingSite}
                  onChange={async (e) => {
                    const nextTenantId = e.target.value
                    if (!nextTenantId || nextTenantId === activeSiteTenantId) return
                    setSwitchingSite(true)
                    try {
                      await switchSite(nextTenantId)
                      setShowMore(false)
                    } finally {
                      setSwitchingSite(false)
                    }
                  }}
                  className="h-11 w-full rounded-lg px-2.5 text-base"
                  style={{ backgroundColor: 'var(--ms-bg)', border: '1px solid var(--ms-border-strong)', color: 'var(--ms-text)' }}
                >
                  {availableSites.map(site => (
                    <option key={site.tenant_id} value={site.tenant_id}>{site.tenant_name}</option>
                  ))}
                </select>
              </div>
            )}
            <div className="grid grid-cols-4 gap-0">
              {moreMenuItems.map((item) => (
                <button
                  key={item.to}
                  type="button"
                  onClick={() => { navigate(item.to); setShowMore(false) }}
                  className="flex flex-col items-center gap-1.5 py-4 px-2 text-center transition-colors active:opacity-60"
                  style={{ color: 'var(--ms-text-mid)' }}
                >
                  <item.icon size={20} />
                  <span className="text-xs font-medium leading-tight">{item.label}</span>
                </button>
              ))}
              <button
                type="button"
                onClick={() => { setShowChangelog(true); setShowMore(false) }}
                className="flex flex-col items-center gap-1.5 py-4 px-2 text-center transition-colors active:opacity-60"
                style={{ color: 'var(--ms-text-mid)' }}
              >
                <Sparkles size={20} />
                <span className="text-xs font-medium leading-tight">What's new</span>
              </button>
            </div>
            <button
              type="button"
              onClick={() => { logout(); setShowMore(false) }}
              className="flex min-h-12 w-full items-center justify-center gap-2 text-sm font-medium"
              style={{ color: 'var(--ms-error)', borderTop: '1px solid var(--ms-border)' }}
            >
              <LogOut size={16} />
              Sign out
            </button>
          </div>
        </div>
      )}

      {/* Bottom tab bar */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-30 flex items-stretch"
        style={{
          backgroundColor: 'var(--ms-surface)',
          borderTop: '1px solid var(--ms-border)',
          paddingBottom: 'env(safe-area-inset-bottom)',
          height: 'var(--ms-mobile-bar-h)',
        }}
        aria-label="Primary navigation"
      >
        {/* Dashboard */}
        <NavLink
          to="/dashboard"
          className="flex flex-1 flex-col items-center justify-center gap-1 pt-2 transition-colors active:opacity-60"
          style={({ isActive }) => tabStyle(isActive)}
        >
          {({ isActive }) => (
            <>
              <LayoutDashboard size={22} strokeWidth={isActive ? 2.5 : 1.8} />
              <span className="text-[10px] font-medium">Home</span>
            </>
          )}
        </NavLink>

        {/* Inbox */}
        {!demoModeEnabled && (
        <NavLink
          to="/inbox"
          className="flex flex-1 flex-col items-center justify-center gap-1 pt-2 transition-colors active:opacity-60"
          style={({ isActive }) => tabStyle(isActive)}
        >
          {({ isActive }) => (
            <>
              <div className="relative">
                <Inbox size={22} strokeWidth={isActive ? 2.5 : 1.8} />
                {inboxCount > 0 && (
                  <span className="absolute -top-1 -right-2 text-[9px] font-bold px-1 rounded-full min-w-[14px] text-center leading-[14px]" style={{ backgroundColor: 'var(--ms-error)', color: '#fff' }}>
                    {inboxCount > 99 ? '99+' : inboxCount}
                  </span>
                )}
              </div>
              <span className="text-[10px] font-medium">Inbox</span>
            </>
          )}
        </NavLink>
        )}
        {demoModeEnabled && (
        <NavLink
          to="/customers"
          className="flex flex-1 flex-col items-center justify-center gap-1 pt-2 transition-colors active:opacity-60"
          style={({ isActive }) => tabStyle(isActive)}
        >
          {({ isActive }) => (
            <>
              <Users size={22} strokeWidth={isActive ? 2.5 : 1.8} />
              <span className="text-[10px] font-medium">Customers</span>
            </>
          )}
        </NavLink>
        )}

        {/* Service tabs (up to 2) */}
        {primaryServiceTabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={false}
            className="flex flex-1 flex-col items-center justify-center gap-1 pt-2 transition-colors active:opacity-60"
            style={({ isActive }) => tabStyle(isActive)}
          >
            {({ isActive }) => (
              <>
                <tab.icon size={22} strokeWidth={isActive ? 2.5 : 1.8} />
                <span className="text-[10px] font-medium">{tab.label}</span>
              </>
            )}
          </NavLink>
        ))}

        {/* More */}
        <button
          type="button"
          onClick={() => setShowMore((v) => !v)}
          className={cn(
            'flex flex-1 flex-col items-center justify-center gap-1 pt-2 transition-colors active:opacity-60',
            showMore ? '' : '',
          )}
          style={{ color: showMore ? 'var(--ms-accent)' : 'var(--ms-text-muted)' }}
          aria-label="More navigation options"
        >
          <MoreHorizontal size={22} strokeWidth={showMore ? 2.5 : 1.8} />
          <span className="text-[10px] font-medium">More</span>
        </button>
      </nav>

      {showChangelog && <ChangelogModal onClose={() => setShowChangelog(false)} />}
    </>
  )
}
