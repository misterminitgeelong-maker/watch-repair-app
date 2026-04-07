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

/**
 * Mobile bottom tab bar — only shown on screens < md (768px).
 * Tabs are driven by feature flags so subscribers only see what they pay for.
 */
export default function BottomTabBar() {
  const { hasFeature, logout } = useAuth()
  const navigate = useNavigate()
  const [showMore, setShowMore] = useState(false)
  const [showChangelog, setShowChangelog] = useState(false)

  const hasWatch = hasFeature('watch')
  const hasShoe = hasFeature('shoe')
  const hasMobile = hasFeature('auto_key')

  // Build the primary tabs dynamically based on features
  // Always: Dashboard, Inbox
  // Then up to 2 service tabs based on subscription
  // Always ends with: More
  const serviceTabs = [
    hasWatch && { to: '/jobs', label: 'Watch', icon: Wrench },
    hasShoe && { to: '/shoe-repairs', label: 'Shoe', icon: Scissors },
    hasMobile && { to: '/auto-key', label: 'Mobile', icon: KeyRound },
    // If none of the above, show Customers as a fallback service tab
    (!hasWatch && !hasShoe && !hasMobile) && { to: '/customers', label: 'Customers', icon: Users },
  ].filter(Boolean) as Array<{ to: string; label: string; icon: typeof Wrench }>

  // If there are more than 2 service tabs, keep only the first 2 and push the rest into More
  const primaryServiceTabs = serviceTabs.slice(0, 2)

  const moreMenuItems = [
    serviceTabs.length > 2 && serviceTabs[2],
    { to: '/customers', label: 'Customers', icon: Users },
    { to: '/invoices', label: 'Invoices', icon: Receipt },
    { to: '/reports', label: 'Reports', icon: BarChart3 },
    { to: '/stocktakes', label: 'Stocktake', icon: ClipboardList },
    hasFeature('customer_accounts') && { to: '/customer-accounts', label: 'Accounts', icon: Building2 },
    hasFeature('multi_site') && { to: '/parent-account', label: 'Parent', icon: Building2 },
    { to: '/database', label: 'Database', icon: Database },
    { to: '/accounts', label: 'Settings', icon: UserCog },
  ].filter(Boolean) as Array<{ to: string; label: string; icon: typeof Wrench }>

  const tabStyle = (isActive: boolean) => ({
    color: isActive ? 'var(--cafe-amber)' : 'var(--cafe-text-muted)',
  })

  return (
    <>
      {/* More menu overlay */}
      {showMore && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setShowMore(false)}>
          <div className="absolute inset-0" style={{ backgroundColor: 'rgba(0,0,0,0.3)' }} />
          <div
            className="absolute bottom-16 left-0 right-0 mx-3 rounded-2xl overflow-hidden shadow-2xl"
            style={{ backgroundColor: 'var(--cafe-surface)', border: '1px solid var(--cafe-border)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="grid grid-cols-4 gap-0">
              {moreMenuItems.map((item) => (
                <button
                  key={item.to}
                  type="button"
                  onClick={() => { navigate(item.to); setShowMore(false) }}
                  className="flex flex-col items-center gap-1.5 py-4 px-2 text-center transition-colors active:opacity-60"
                  style={{ color: 'var(--cafe-text-mid)' }}
                >
                  <item.icon size={20} />
                  <span className="text-xs font-medium leading-tight">{item.label}</span>
                </button>
              ))}
              <button
                type="button"
                onClick={() => { setShowChangelog(true); setShowMore(false) }}
                className="flex flex-col items-center gap-1.5 py-4 px-2 text-center transition-colors active:opacity-60"
                style={{ color: 'var(--cafe-text-mid)' }}
              >
                <Sparkles size={20} />
                <span className="text-xs font-medium leading-tight">What's new</span>
              </button>
              <button
                type="button"
                onClick={() => { logout(); setShowMore(false) }}
                className="flex flex-col items-center gap-1.5 py-4 px-2 text-center transition-colors active:opacity-60"
                style={{ color: '#C96A5A' }}
              >
                <LogOut size={20} />
                <span className="text-xs font-medium leading-tight">Sign out</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom tab bar */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-30 flex items-stretch"
        style={{
          backgroundColor: 'var(--cafe-surface)',
          borderTop: '1px solid var(--cafe-border)',
          paddingBottom: 'env(safe-area-inset-bottom)',
          height: 'calc(56px + env(safe-area-inset-bottom))',
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
        <NavLink
          to="/inbox"
          className="flex flex-1 flex-col items-center justify-center gap-1 pt-2 transition-colors active:opacity-60"
          style={({ isActive }) => tabStyle(isActive)}
        >
          {({ isActive }) => (
            <>
              <Inbox size={22} strokeWidth={isActive ? 2.5 : 1.8} />
              <span className="text-[10px] font-medium">Inbox</span>
            </>
          )}
        </NavLink>

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
          style={{ color: showMore ? 'var(--cafe-amber)' : 'var(--cafe-text-muted)' }}
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
