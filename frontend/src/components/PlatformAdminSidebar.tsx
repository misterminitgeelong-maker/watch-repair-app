import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { BarChart3, Building2, CreditCard, LogOut, ScrollText, Users } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'

/**
 * Navigation for a platform admin in their own workspace. That workspace is
 * not a shop, so the shop sidebar (jobs, customers, Minit pages) only led to
 * empty screens and errors; the admin gets just the console.
 * Entering a shop switches to that shop's normal sidebar.
 */
export const PLATFORM_ADMIN_NAV = [
  { to: '/platform-admin/shops', label: 'Shops', icon: Building2 },
  { to: '/platform-admin/billing', label: 'Billing', icon: CreditCard },
  { to: '/platform-admin/audit', label: 'Audit log', icon: ScrollText },
  { to: '/platform-admin/users', label: 'Users', icon: Users },
  { to: '/platform-admin/reports', label: 'Reports', icon: BarChart3 },
] as const

export default function PlatformAdminSidebar({
  className,
  mobile = false,
  onNavigate,
  onClose,
  closeIcon,
}: {
  className?: string
  mobile?: boolean
  onNavigate?: () => void
  onClose?: () => void
  closeIcon?: ReactNode
}) {
  const { logout } = useAuth()
  const linkStyle = (isActive: boolean) =>
    isActive
      ? { backgroundColor: 'var(--ms-sidebar-active)', color: 'var(--ms-sidebar-act-text)', border: '1px solid var(--ms-sidebar-border)' }
      : { color: 'var(--ms-sidebar-text)' }

  return (
    <aside
      className={cn('w-[216px] flex min-h-0 shrink-0 flex-col md:h-full', className)}
      style={{
        backgroundColor: 'var(--ms-sidebar)',
        color: 'var(--ms-sidebar-text)',
        ...(!mobile ? { borderRight: '1px solid var(--ms-sidebar-border)' } : {}),
      }}
      data-nav="platform-admin"
    >
      <div className={mobile ? 'px-6 py-6' : 'px-6 pt-8 pb-7'} style={{ borderBottom: '1px solid var(--ms-sidebar-border)' }}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <img src="/mainspring-logo.svg" alt="Mainspring" style={{ width: mobile ? 120 : 148, height: 'auto', display: 'block' }} />
            <p className="mt-2 text-[11px] font-semibold uppercase tracking-[0.2em]" style={{ color: 'var(--ms-sidebar-text)' }}>
              Platform admin
            </p>
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

      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto px-3 py-6" aria-label="Platform admin">
        {PLATFORM_ADMIN_NAV.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn('relative flex items-center gap-3 rounded-lg px-3.5 py-3 text-sm font-medium transition-all duration-150 min-h-11', isActive && 'font-semibold')
            }
            style={({ isActive }) => linkStyle(isActive)}
          >
            <item.icon size={16} style={{ flexShrink: 0 }} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="shrink-0 px-3 pb-6" style={{ borderTop: '1px solid var(--ms-sidebar-border)', paddingTop: '1.25rem' }}>
        <button
          onClick={() => {
            logout()
            onNavigate?.()
          }}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150"
          style={{ color: 'var(--ms-sidebar-text)' }}
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </aside>
  )
}
