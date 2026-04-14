import { useState, type ReactNode } from 'react'
import { useInboxCount } from '@/pages/InboxPage'
import { useInstallPrompt } from '@/hooks/useInstallPrompt'
import { NavLink, useLocation } from 'react-router-dom'
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
  Download,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import ChangelogModal from './ChangelogModal'
import { cn } from '@/lib/utils'
import type { FeatureKey } from '@/lib/api'

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
  const inboxCount = useInboxCount()
  const [showChangelog, setShowChangelog] = useState(false)
  const [showIosHint, setShowIosHint] = useState(false)
  const { pathname } = useLocation()
  const { canInstall, isIos, isStandalone, promptInstall } = useInstallPrompt()
  const showInstall = !isStandalone && (canInstall || isIos)

  const filterItems = (items: NavLinkItem[]) =>
    items.filter((item) => !item.feature || hasFeature(item.feature))

  const filteredBefore = filterItems(navBeforeMobile)
  const filteredAfter = filterItems(navAfterMobile)
  const showMobile = hasFeature('auto_key')
  const insideMobile = pathname.startsWith('/auto-key')

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
          <img
            src="/mainspring-logo.svg"
            alt="Mainspring"
            style={{
              width: mobile ? 'min(100%, 152px)' : 'min(100%, 168px)',
              maxWidth: '100%',
              height: 'auto',
              display: 'block',
              objectFit: 'contain',
            }}
          />

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
                {item.to === '/inbox' && inboxCount > 0 && (
                  <span className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center" style={{ backgroundColor: '#C96A5A', color: '#fff' }}>
                    {inboxCount > 99 ? '99+' : inboxCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}

        {showMobile && (
          <>
            <NavLink
              to="/auto-key"
              end={false}
              title="Jobs, POS, dispatch, map, planner, reports — Prospects and Toolkit appear below when you are in this area"
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
                  <KeyRound size={16} style={{ color: isActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                  Mobile Services
                </>
              )}
            </NavLink>
            {insideMobile && (
              <div
                className="mt-0.5 mb-1 ml-2 pl-3 space-y-0.5"
                style={{ borderLeft: '2px solid rgba(200,168,130,0.4)' }}
              >
                <NavLink
                  to="/auto-key/team"
                  title="Technicians and Mobile Services commission settings"
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
                      <Users size={16} style={{ color: isActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                      Team
                    </>
                  )}
                </NavLink>
                <NavLink
                  to="/auto-key/prospects"
                  title="B2B prospect search and lead lists"
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
                      <Target size={16} style={{ color: isActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                      Prospects
                    </>
                  )}
                </NavLink>
                <NavLink
                  to="/auto-key/toolkit"
                  title="Van tool inventory and scenario recommendations"
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
                      <Toolbox size={16} style={{ color: isActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                      Toolkit
                    </>
                  )}
                </NavLink>
              </div>
            )}
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
        {showInstall && (
          <div className="mb-2 px-1">
            <button
              onClick={() => {
                if (isIos) { setShowIosHint(true) } else { void promptInstall() }
                onNavigate?.()
              }}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150"
              style={{ color: '#C8A882', backgroundColor: 'rgba(201,162,72,0.08)', border: '1px solid rgba(201,162,72,0.2)' }}
              onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'rgba(201,162,72,0.15)')}
              onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'rgba(201,162,72,0.08)')}
            >
              <Download size={15} />
              Install app
            </button>
          </div>
        )}
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
      {showIosHint && (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center p-4"
          style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
          onClick={() => setShowIosHint(false)}
        >
          <div
            className="w-full max-w-sm rounded-2xl p-6 text-center space-y-3"
            style={{ backgroundColor: 'var(--cafe-paper)', color: 'var(--cafe-text)' }}
            onClick={e => e.stopPropagation()}
          >
            <p className="text-base font-semibold" style={{ fontFamily: "'Playfair Display', Georgia, serif" }}>
              Add to Home Screen
            </p>
            <p className="text-sm" style={{ color: 'var(--cafe-text-muted)' }}>
              Tap the <strong>Share</strong> icon <span style={{ fontSize: '1.1em' }}>⎙</span> at the bottom of Safari, then choose <strong>"Add to Home Screen"</strong> to install Mainspring.
            </p>
            <button
              className="mt-1 w-full rounded-xl py-2.5 text-sm font-semibold"
              style={{ backgroundColor: 'var(--cafe-amber)', color: '#fff' }}
              onClick={() => setShowIosHint(false)}
            >
              Got it
            </button>
          </div>
        </div>
      )}
    </aside>
  )
}
