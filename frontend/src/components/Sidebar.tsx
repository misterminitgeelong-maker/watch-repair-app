import { NavLink } from 'react-router-dom'
import { WatchIcon, Users, Wrench, FileText, Receipt, LayoutDashboard, LogOut, Database } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/jobs', label: 'Repair Jobs', icon: Wrench },
  { to: '/quotes', label: 'Quotes', icon: FileText },
  { to: '/invoices', label: 'Invoices', icon: Receipt },
  { to: '/database', label: 'Database', icon: Database },
]

export default function Sidebar() {
  const { logout } = useAuth()

  return (
    <aside
      className="w-60 flex flex-col shrink-0"
      style={{ backgroundColor: 'var(--cafe-espresso)', color: 'var(--cafe-sidebar-txt)' }}
    >
      {/* Branding */}
      <div
        className="px-6 py-6"
        style={{ borderBottom: '1px solid var(--cafe-espresso-3)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center shrink-0"
            style={{ backgroundColor: 'var(--cafe-gold)', color: 'var(--cafe-espresso)' }}
          >
            <WatchIcon size={17} strokeWidth={2.5} />
          </div>
          <div>
            <p
              className="text-[15px] font-semibold leading-tight tracking-tight"
              style={{ fontFamily: "'Playfair Display', Georgia, serif", color: '#F5E8CA' }}
            >
              WatchRepair
            </p>
            <p
              className="text-[10px] tracking-[0.18em] uppercase mt-0.5"
              style={{ color: '#7A5038' }}
            >
              Atelier
            </p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-5 space-y-0.5">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
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
            onClick={logout}
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
