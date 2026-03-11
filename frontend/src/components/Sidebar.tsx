import { NavLink } from 'react-router-dom'
import { Users, Wrench, Receipt, LayoutDashboard, LogOut, Database, BarChart3 } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/jobs', label: 'Repair Jobs', icon: Wrench },
  { to: '/invoices', label: 'Invoices', icon: Receipt },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/database', label: 'Database', icon: Database },
]

interface SidebarProps {
  className?: string
  mobile?: boolean
  onNavigate?: () => void
  onClose?: () => void
  closeIcon?: React.ReactNode
}

export default function Sidebar({ className, mobile = false, onNavigate, onClose, closeIcon }: SidebarProps) {
  const { logout } = useAuth()

  return (
    <aside
      className={cn('w-60 flex flex-col shrink-0', className)}
      style={{ backgroundColor: 'var(--cafe-espresso)', color: 'var(--cafe-sidebar-txt)' }}
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
      <nav className="flex-1 px-3 py-5 space-y-0.5">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150',
                isActive
                  ? 'font-semibold'
                  : 'hover:text-[#F5E8CA]'
              )
            }
            style={({ isActive }) =>
              isActive
                ? { backgroundColor: 'var(--cafe-gold)', color: 'var(--cafe-espresso)' }
                : { color: 'var(--cafe-sidebar-txt)' }
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={16} style={isActive ? { color: 'var(--cafe-espresso)' } : {}} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Sign out */}
      <div className="px-3 pb-6">
        <div style={{ borderTop: '1px solid var(--cafe-espresso-3)', paddingTop: '1rem' }}>
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
