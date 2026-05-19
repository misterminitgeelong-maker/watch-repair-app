import { useState, type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { MoreHorizontal } from 'lucide-react'
import { useInboxCount } from '@/pages/InboxPage'
import { MINIT_HQ_NAV } from './MinitHqSidebar'
import { cn } from '@/lib/utils'

/** Mobile bottom nav for Minit HQ — mirrors the six-item desktop sidebar. */
export default function MinitHqBottomTabBar() {
  const inboxCount = useInboxCount()
  const navigate = useNavigate()
  const [showMore, setShowMore] = useState(false)

  const primary = MINIT_HQ_NAV.slice(0, 3)
  const moreItems = MINIT_HQ_NAV.slice(3)

  const tabStyle = (isActive: boolean) => ({
    color: isActive ? 'var(--ms-accent)' : 'var(--ms-text-muted)',
  })

  return (
    <>
      {showMore && (
        <HqMoreSheet onClose={() => setShowMore(false)}>
          <div className="grid grid-cols-3 gap-0">
            {moreItems.map((item) => (
              <button
                key={item.to}
                type="button"
                onClick={() => {
                  navigate(item.to)
                  setShowMore(false)
                }}
                className="flex flex-col items-center gap-1.5 py-4 px-2 text-center transition-colors active:opacity-60"
                style={{ color: 'var(--ms-text-mid)' }}
              >
                <item.icon size={20} />
                <span className="text-xs font-medium leading-tight">{item.label}</span>
              </button>
            ))}
          </div>
        </HqMoreSheet>
      )}

      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 z-30 flex items-stretch"
        style={{
          backgroundColor: 'var(--ms-surface)',
          borderTop: '1px solid var(--ms-border)',
          paddingBottom: 'env(safe-area-inset-bottom)',
          height: 'calc(56px + env(safe-area-inset-bottom))',
        }}
        data-nav="minit-hq"
        aria-label="Minit HQ"
      >
        {primary.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/minit/dashboard'}
            className="relative flex flex-1 flex-col items-center justify-center gap-1 pt-2 transition-colors active:opacity-60"
            style={({ isActive }) => tabStyle(isActive)}
          >
            {({ isActive }) => (
              <>
                <item.icon size={22} strokeWidth={isActive ? 2.5 : 1.8} />
                <span className="text-[10px] font-medium">{item.label}</span>
                {item.to === '/minit/inbox' && inboxCount > 0 && (
                  <span
                    className="absolute top-0.5 right-3 text-[9px] font-bold px-1 rounded-full min-w-[14px] text-center leading-[14px]"
                    style={{ backgroundColor: '#C96A5A', color: '#fff' }}
                  >
                    {inboxCount > 99 ? '99+' : inboxCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
        <button
          type="button"
          onClick={() => setShowMore((v) => !v)}
          className={cn(
            'flex flex-1 flex-col items-center justify-center gap-1 pt-2 transition-colors active:opacity-60',
          )}
          style={{ color: showMore ? 'var(--ms-accent)' : 'var(--ms-text-muted)' }}
          aria-label="More Minit HQ pages"
        >
          <MoreHorizontal size={22} strokeWidth={showMore ? 2.5 : 1.8} />
          <span className="text-[10px] font-medium">More</span>
        </button>
      </nav>
    </>
  )
}

function HqMoreSheet({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40 md:hidden" onClick={onClose}>
      <div className="absolute inset-0" style={{ backgroundColor: 'rgba(0,0,0,0.3)' }} />
      <div
        className="absolute bottom-16 left-0 right-0 mx-3 rounded-2xl overflow-hidden shadow-2xl"
        style={{ backgroundColor: 'var(--ms-surface)', border: '1px solid var(--ms-border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}
