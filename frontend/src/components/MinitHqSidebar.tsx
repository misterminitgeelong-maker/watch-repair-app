import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  LogOut,
  BarChart3,
  Building2,
  KeyRound,
  Inbox,
  Sparkles,
  Download,
  Route,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { useInboxCount } from '@/hooks/useInboxCount'
import { useInstallPrompt } from '@/hooks/useInstallPrompt'
import ChangelogModal from './ChangelogModal'
import { cn } from '@/lib/utils'
import { APP_BUILD_ID } from '@/lib/buildInfo'

/** Single source of truth — Minit HQ sidebar links (no feature gates). */
export const MINIT_HQ_NAV = [
  { to: '/minit/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/minit/inbox', label: 'Inbox', icon: Inbox, title: 'Website leads, email enquiries, and HQ alerts' },
  { to: '/minit/shops', label: 'Shops', icon: Building2, title: 'Browse the retail network by region' },
  { to: '/minit/lead-routing', label: 'Lead routing', icon: Route, title: 'Website ingest, dispatch, and territory map' },
  { to: '/minit/mobile-services', label: 'Mobile jobs', icon: KeyRound, title: 'Network mobile job report' },
  { to: '/minit/reports', label: 'Reports', icon: BarChart3, title: 'Shop analytics and troubleshooting' },
] as const

export interface MinitHqSidebarProps {
  className?: string
  mobile?: boolean
  onNavigate?: () => void
  onClose?: () => void
  closeIcon?: ReactNode
}

export default function MinitHqSidebar({
  className,
  mobile = false,
  onNavigate,
  onClose,
  closeIcon,
}: MinitHqSidebarProps) {
  const { logout } = useAuth()
  const inboxCount = useInboxCount()
  const [showChangelog, setShowChangelog] = useState(false)
  const [showIosHint, setShowIosHint] = useState(false)
  const { canInstall, isIos, isStandalone, promptInstall } = useInstallPrompt()
  const showInstall = !isStandalone && (canInstall || isIos)

  function linkClasses(isActive: boolean) {
    return cn(
      'relative flex items-center gap-3 rounded-lg px-3.5 py-3 text-sm font-medium transition-all duration-150 min-h-11',
      isActive ? 'font-semibold' : '',
    )
  }

  function linkStyle(isActive: boolean) {
    return isActive
      ? {
          backgroundColor: 'var(--ms-sidebar-active)',
          color: 'var(--ms-sidebar-act-text)',
          border: '1px solid var(--ms-sidebar-border)',
        }
      : { color: 'var(--ms-sidebar-text)' }
  }

  return (
    <aside
      className={cn('w-[216px] flex min-h-0 shrink-0 flex-col md:h-full', className)}
      style={{
        backgroundColor: 'var(--ms-sidebar)',
        color: 'var(--ms-sidebar-text)',
        ...(!mobile ? { borderRight: '1px solid var(--ms-sidebar-border)' } : {}),
      }}
      data-nav="minit-hq"
      data-build={APP_BUILD_ID}
    >
      <div
        className={mobile ? 'px-6 py-6' : 'px-6 pt-8 pb-7'}
        style={{ borderBottom: '1px solid var(--cafe-espresso-3)' }}
      >
        <div className="flex items-center justify-between gap-3">
          <div
            style={{
              backgroundColor: '#fff',
              borderRadius: 8,
              padding: '6px 10px',
              display: 'inline-block',
            }}
          >
            <img
              src="/minit-logo.jpg"
              alt="Mister Minit"
              style={{
                width: mobile ? 'min(100%, 120px)' : 'min(100%, 148px)',
                height: 'auto',
                display: 'block',
                objectFit: 'contain',
              }}
            />
          </div>
          {mobile && onClose && (
            <button
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg"
              onClick={onClose}
              style={{ color: 'var(--ms-sidebar-text)' }}
              aria-label="Close navigation"
            >
              {closeIcon}
            </button>
          )}
        </div>
      </div>

      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 py-6" aria-label="Minit HQ">
        {MINIT_HQ_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            title={'title' in item ? item.title : undefined}
            end={item.to === '/minit/dashboard' || item.to === '/minit/lead-routing'}
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
                      backgroundColor: 'var(--ms-accent)',
                    }}
                  />
                )}
                <item.icon
                  size={16}
                  style={{ color: isActive ? 'var(--ms-sidebar-act-text)' : undefined, flexShrink: 0 }}
                />
                {item.label}
                {item.to === '/minit/inbox' && inboxCount > 0 && (
                  <span
                    className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center"
                    style={{ backgroundColor: '#C96A5A', color: '#fff' }}
                  >
                    {inboxCount > 99 ? '99+' : inboxCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="shrink-0 px-3 pb-6">
        {showInstall && (
          <div className="mb-2 px-1">
            <button
              onClick={() => {
                if (isIos) {
                  setShowIosHint(true)
                } else {
                  void promptInstall()
                }
                onNavigate?.()
              }}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150"
              style={{
                color: 'var(--ms-sidebar-text)',
                backgroundColor: 'var(--ms-sidebar-hover)',
                border: '1px solid var(--ms-sidebar-border)',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--ms-sidebar-active)')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'var(--ms-sidebar-hover)')}
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
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 hover:text-[var(--ms-sidebar-act-text)]"
            style={{ color: 'var(--ms-sidebar-text)' }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--ms-sidebar-hover)')}
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
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 hover:text-[var(--ms-sidebar-act-text)]"
            style={{ color: 'var(--ms-sidebar-text)' }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--ms-sidebar-hover)')}
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
          style={{ backgroundColor: 'var(--ms-overlay)' }}
          onClick={() => setShowIosHint(false)}
        >
          <div
            className="w-full max-w-sm rounded-2xl p-6 text-center space-y-3"
            style={{ backgroundColor: 'var(--ms-surface)', color: 'var(--ms-text)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-base font-semibold">Add to Home Screen</p>
            <p className="text-sm" style={{ color: 'var(--ms-text-muted)' }}>
              Tap the <strong>Share</strong> icon at the bottom of Safari, then choose{' '}
              <strong>&quot;Add to Home Screen&quot;</strong>.
            </p>
            <button
              className="mt-1 w-full rounded-xl py-2.5 text-sm font-semibold"
              style={{ backgroundColor: 'var(--ms-accent)', color: '#fff' }}
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
