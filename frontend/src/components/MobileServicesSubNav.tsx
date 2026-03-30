import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const tabs = [
  { to: '/auto-key', label: 'Jobs & dispatch', end: true },
  { to: '/auto-key/team', label: 'Team', end: true },
  { to: '/auto-key/prospects', label: 'Prospects', end: true },
  { to: '/auto-key/toolkit', label: 'Toolkit', end: true },
] as const

/** Secondary navigation for Mobile Services (jobs board, prospects, toolkit). */
export default function MobileServicesSubNav({ className }: { className?: string }) {
  return (
    <div
      className={cn('flex flex-wrap gap-2', className)}
      role="navigation"
      aria-label="Mobile services sections"
    >
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) =>
            cn(
              'rounded-lg px-3.5 py-2.5 text-sm font-medium transition-colors min-h-11 inline-flex items-center',
              isActive
                ? 'shadow-sm'
                : '',
            )
          }
          style={({ isActive }) =>
            isActive
              ? { backgroundColor: 'var(--cafe-amber)', color: '#2C1810' }
              : { backgroundColor: 'var(--cafe-surface)', color: 'var(--cafe-text-muted)' }
          }
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  )
}

/** True when pathname is a job detail UUID under /auto-key (not prospects/toolkit). */
export function isAutoKeyJobDetailPath(pathname: string): boolean {
  if (!pathname.startsWith('/auto-key/')) return false
  const rest = pathname.slice('/auto-key/'.length)
  if (!rest || rest.includes('/')) return false
  if (rest === 'prospects' || rest === 'toolkit' || rest === 'team') return false
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(rest)
}
