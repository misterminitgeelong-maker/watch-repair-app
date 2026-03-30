import { useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import {
  Users,
  Wrench,
  Receipt,
  LayoutDashboard,
  LogOut,
  Database,
  BarChart3,
  UserCog,
  Scissors,
  KeyRound,
  Building2,
  ClipboardList,
  Sparkles,
  Inbox,
  Toolbox,
  Target,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import ChangelogModal from './ChangelogModal'
import { cn } from '@/lib/utils'
import type { FeatureKey } from '@/lib/api'
import { isAutoKeyJobDetailPath } from '@/components/MobileServicesSubNav'

type NavLinkItem = {
  to: string
  label: string
  icon: typeof LayoutDashboard
  feature?: FeatureKey
  title?: string
}

const navBeforeMobile: NavLinkItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/inbox', label: 'Inbox', icon: Inbox, title: 'Quote activity and website mobile key leads' },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/jobs', label: 'Watch Repairs', icon: Wrench, feature: 'watch' },
  { to: '/shoe-repairs', label: 'Shoe Repairs', icon: Scissors, feature: 'shoe' },
]

const navMobile: NavLinkItem[] = [
  {
    to: '/auto-key',
    label: 'Jobs & dispatch',
    icon: KeyRound,
    title: 'Board, POS, dispatch, map, planner, reports',
  },
  { to: '/auto-key/prospects', label: 'Prospects', icon: Target, title: 'B2B prospect search and lead lists' },
  {
    to: '/auto-key/toolkit',
    label: 'Toolkit',
    icon: Toolbox,
    title: 'Van tool inventory and scenario recommendations',
  },
]

const navAfterMobile: NavLinkItem[] = [
  { to: '/customer-accounts', label: 'Customer Accounts', icon: Building2, feature: 'customer_accounts' },
  { to: '/parent-account', label: 'Parent Account', icon: Building2, feature: 'multi_site' },
  { to: '/invoices', label: 'Invoices', icon: Receipt },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/stocktakes', label: 'Stocktake', icon: ClipboardList },
  { to: '/database', label: 'Database', icon: Database },
  { to: '/accounts', label: 'Accounts', icon: UserCog },
]

interface SidebarProps {
  className?: string
  mobile?: boolean
  onNavigate?: () => void
  onClose?: () => void
  closeIcon?: ReactNode
}

export default function Sidebar({ className, mobile = false, onNavigate, onClose, closeIcon }: SidebarProps) {
  const { logout, role, hasFeature } = useAuth()
  const [showChangelog, setShowChangelog] = useState(false)
  const { pathname } = useLocation()

  const filterItems = (items: NavLinkItem[]) =>
    items.filter((item) => !item.feature || hasFeature(item.feature))

  const filteredBefore = filterItems(navBeforeMobile)
  const filteredAfter = filterItems(navAfterMobile)
  const showMobile = hasFeature('auto_key')
  const jobsBoardActive = pathname === '/auto-key' || isAutoKeyJobDetailPath(pathname)

  function linkClasses(isActive: boolean, opts?: { indent?: boolean }) {
    return cn(
      'relative flex items-center gap-3 rounded-lg px-3.5 py-3 text-sm font-medium transition-all duration-150 min-h-11',
      opts?.indent && 'pl-6',
      isActive ? 'font-semibold' : '',
    )
  }

  function linkStyle(isActive: boolean) {
    return isActive
      ? { backgroundColor: 'rgba(255,255,255,0.06)', color: '#F0E7DD', border: '1px solid rgba(255,255,255,0.08)' }
      : { color: 'var(--cafe-sidebar-txt)' }
  }

  return (
    <aside
      className={cn('w-60 flex flex-col shrink-0', className)}
      style={{
        backgroundColor: 'var(--cafe-espresso)',
        color: 'var(--cafe-sidebar-txt)',
        ...(!mobile ? { borderRight: '1px solid rgba(160,130,90,0.15)' } : {}),
      }}
    >
      <div className="px-6 py-6" style={{ borderBottom: '1px solid var(--cafe-espresso-3)' }}>
        <div className="flex items-center justify-between gap-3">
          <img src="/mainspring-logo.png" alt="Mainspring" className="h-9 w-auto rounded" style={{ maxWidth: '160px' }} />

          {mobile && onClose && (
            <button
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg"
              onClick={onClose}
              style={{ color: '#C8A882' }}
              aria-label="Close navigation"
            >
              {closeIcon}
            </button>
          )}
        </div>
      </div>

      <nav className="flex-1 px-3 py-6 space-y-1">
        {filteredBefore.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            title={item.title}
            end={item.to === '/'}
            onClick={onNavigate}
            className={({ isActive }) => linkClasses(isActive)}
            style={({ isActive }) => linkStyle(isActive)}
            onMouseEnter={(e) => {
              const el = e.currentTarget
              if (!el.getAttribute('aria-current')) el.style.backgroundColor = 'rgba(255,255,255,0.05)'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget
              if (!el.getAttribute('aria-current')) el.style.backgroundColor = 'transparent'
            }}
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: '20%',
                      bottom: '20%',
                      width: 3,
                      borderRadius: 4,
                      backgroundColor: 'var(--cafe-gold)',
                    }}
                  />
                )}
                <item.icon size={16} style={{ color: isActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                {item.label}
              </>
            )}
          </NavLink>
        ))}

        {showMobile && (
          <>
            <div
              className="px-3.5 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider"
              style={{ color: 'rgba(200,168,130,0.75)' }}
            >
              Mobile services
            </div>
            {navMobile.map((item) => {
              if (item.to === '/auto-key') {
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    title={item.title}
                    onClick={onNavigate}
                    className={linkClasses(jobsBoardActive, { indent: true })}
                    style={linkStyle(jobsBoardActive)}
                    aria-current={jobsBoardActive ? 'page' : undefined}
                    onMouseEnter={(e) => {
                      const el = e.currentTarget
                      if (!jobsBoardActive) el.style.backgroundColor = 'rgba(255,255,255,0.05)'
                    }}
                    onMouseLeave={(e) => {
                      const el = e.currentTarget
                      if (!jobsBoardActive) el.style.backgroundColor = 'transparent'
                    }}
                  >
                    {jobsBoardActive && (
                      <span
                        style={{
                          position: 'absolute',
                          left: 0,
                          top: '20%',
                          bottom: '20%',
                          width: 3,
                          borderRadius: 4,
                          backgroundColor: 'var(--cafe-gold)',
                        }}
                      />
                    )}
                    <item.icon size={16} style={{ color: jobsBoardActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                    {item.label}
                  </Link>
                )
              }
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  title={item.title}
                  end
                  onClick={onNavigate}
                  className={({ isActive }) => linkClasses(isActive, { indent: true })}
                  style={({ isActive }) => linkStyle(isActive)}
                  onMouseEnter={(e) => {
                    const el = e.currentTarget
                    if (!el.getAttribute('aria-current')) el.style.backgroundColor = 'rgba(255,255,255,0.05)'
                  }}
                  onMouseLeave={(e) => {
                    const el = e.currentTarget
                    if (!el.getAttribute('aria-current')) el.style.backgroundColor = 'transparent'
                  }}
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span
                          style={{
                            position: 'absolute',
                            left: 0,
                            top: '20%',
                            bottom: '20%',
                            width: 3,
                            borderRadius: 4,
                            backgroundColor: 'var(--cafe-gold)',
                          }}
                        />
                      )}
                      <item.icon size={16} style={{ color: isActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                      {item.label}
                    </>
                  )}
                </NavLink>
              )
            })}
          </>
        )}

        {filteredAfter.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            title={item.title}
            end={item.to === '/'}
            onClick={onNavigate}
            className={({ isActive }) => linkClasses(isActive)}
            style={({ isActive }) => linkStyle(isActive)}
            onMouseEnter={(e) => {
              const el = e.currentTarget
              if (!el.getAttribute('aria-current')) el.style.backgroundColor = 'rgba(255,255,255,0.05)'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget
              if (!el.getAttribute('aria-current')) el.style.backgroundColor = 'transparent'
            }}
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: '20%',
                      bottom: '20%',
                      width: 3,
                      borderRadius: 4,
                      backgroundColor: 'var(--cafe-gold)',
                    }}
                  />
                )}
                <item.icon size={16} style={{ color: isActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                {item.label}
              </>
            )}
          </NavLink>
        ))}

        {role === 'platform_admin' && (
          <NavLink
            to="/platform-admin/users"
            onClick={onNavigate}
            className={({ isActive }) => linkClasses(isActive)}
            style={({ isActive }) => linkStyle(isActive)}
            onMouseEnter={(e) => {
              const el = e.currentTarget
              if (!el.getAttribute('aria-current')) el.style.backgroundColor = 'rgba(255,255,255,0.05)'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget
              if (!el.getAttribute('aria-current')) el.style.backgroundColor = 'transparent'
            }}
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: '20%',
                      bottom: '20%',
                      width: 3,
                      borderRadius: 4,
                      backgroundColor: 'var(--cafe-gold)',
                    }}
                  />
                )}
                <UserCog size={16} style={{ color: isActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                Platform Admin
              </>
            )}
          </NavLink>
        )}
      </nav>

      <div className="px-3 pb-6">
        <div style={{ borderTop: '1px solid var(--cafe-espresso-3)', paddingTop: '1.25rem' }}>
          <button
            onClick={() => {
              setShowChangelog(true)
              onNavigate?.()
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 hover:text-[#F5E8CA]"
            style={{ color: '#7A5038' }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--cafe-espresso-2)')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            <Sparkles size={16} />
            What&apos;s new
          </button>
          <button
            onClick={() => {
              logout()
              onNavigate?.()
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 hover:text-[#F5E8CA]"
            style={{ color: '#7A5038' }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--cafe-espresso-2)')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </div>
      {showChangelog && <ChangelogModal onClose={() => setShowChangelog(false)} />}
    </aside>
  )
}
