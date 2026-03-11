import { NavLink } from 'react-router-dom'
import { Users, Wrench, Receipt, LayoutDashboard, LogOut, Database, BarChart3, UserCog, Scissors } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/jobs', label: 'Watch Repairs', icon: Wrench },
  { to: '/shoe-repairs', label: 'Shoe Repairs', icon: Scissors },
  { to: '/invoices', label: 'Invoices', icon: Receipt },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/database', label: 'Database', icon: Database },
  { to: '/accounts', label: 'Accounts', icon: UserCog },
]

interface SidebarProps {
  className?: string
  mobile?: boolean
  onNavigate?: () => void
  onClose?: () => void
  closeIcon?: React.ReactNode
}

export default function Sidebar({ className, mobile = false, onNavigate, onClose, closeIcon }: SidebarProps) {
  const { logout, role } = useAuth()

  const navItems = role === 'platform_admin'
    ? [...nav, { to: '/platform-admin/users', label: 'Platform Admin', icon: UserCog }]
    : nav

  return (
    <aside
      className={cn('w-60 flex flex-col shrink-0', className)}
      style={{
        backgroundColor: 'var(--cafe-espresso)',
        color: 'var(--cafe-sidebar-txt)',
        ...(!mobile ? { borderRight: '1px solid rgba(160,130,90,0.15)' } : {}),
      }}
    >
      {/* Branding */}
      <div
        className="px-6 py-6"
        style={{ borderBottom: '1px solid var(--cafe-espresso-3)' }}
      >
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

      {/* Nav */}
      <nav className="flex-1 px-3 py-6 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'relative flex items-center gap-3 rounded-lg px-3.5 py-3 text-sm font-medium transition-all duration-150',
                isActive
                  ? 'font-semibold'
                  : ''
              )
            }
            style={({ isActive }) =>
              isActive
                ? { backgroundColor: 'rgba(255,255,255,0.06)', color: '#F0E7DD', border: '1px solid rgba(255,255,255,0.08)' }
                : { color: 'var(--cafe-sidebar-txt)' }
            }
            onMouseEnter={e => {
              const el = e.currentTarget
              if (!el.getAttribute('aria-current')) el.style.backgroundColor = 'rgba(255,255,255,0.05)'
            }}
            onMouseLeave={e => {
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
                <Icon size={16} style={{ color: isActive ? '#E8D3AE' : undefined, flexShrink: 0 }} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Sign out */}
      <div className="px-3 pb-6">
        <div style={{ borderTop: '1px solid var(--cafe-espresso-3)', paddingTop: '1.25rem' }}>
          <button
            onClick={() => {
              logout()
              onNavigate?.()
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150 hover:text-[#F5E8CA]"
            style={{ color: '#7A5038' }}
            onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--cafe-espresso-2)')}
            onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </div>
    </aside>
  )
}
