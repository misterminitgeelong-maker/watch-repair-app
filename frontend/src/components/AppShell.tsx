import { useState } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { Menu, WatchIcon, X } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import Sidebar from './Sidebar'

export default function AppShell() {
  const { token, initializing } = useAuth()
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  if (initializing) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text-muted)' }}>
        Preparing test session...
      </div>
    )
  }

  if (!token) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="h-screen md:flex" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <Sidebar className="hidden md:flex" />

      <div className="flex min-w-0 flex-1 flex-col">
        <header
          className="md:hidden sticky top-0 z-20 flex items-center justify-between px-4 py-3"
          style={{ backgroundColor: 'var(--cafe-surface)', borderBottom: '1px solid var(--cafe-border)' }}
        >
          <button
            onClick={() => setMobileNavOpen(true)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg"
            style={{ color: 'var(--cafe-text-mid)' }}
            aria-label="Open navigation"
          >
            <Menu size={20} />
          </button>

          <div className="flex items-center gap-2">
            <div
              className="h-7 w-7 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'var(--cafe-gold)', color: 'var(--cafe-espresso)' }}
            >
              <WatchIcon size={14} strokeWidth={2.5} />
            </div>
            <span style={{ fontFamily: "'Playfair Display', Georgia, serif", color: 'var(--cafe-text)' }} className="text-base font-semibold">
              Mainspring
            </span>
          </div>

          <span className="w-9" />
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>

      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            className="absolute inset-0"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.35)' }}
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation overlay"
          />

          <div className="relative h-full w-[84vw] max-w-72">
            <Sidebar
              mobile
              className="h-full"
              onNavigate={() => setMobileNavOpen(false)}
              onClose={() => setMobileNavOpen(false)}
              closeIcon={<X size={18} />}
            />
          </div>
        </div>
      )}
    </div>
  )
}
