import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import Sidebar from './Sidebar'

export default function AppShell() {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />

  return (
    <div className="flex h-screen" style={{ backgroundColor: 'var(--cafe-bg)' }}>
      <Sidebar />
      <main className="flex-1 overflow-y-auto px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}
