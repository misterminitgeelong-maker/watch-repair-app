import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

const CHUNK_RELOAD_KEY = '__ms_chunk_reload'

function isChunkLoadError(error: Error): boolean {
  return error.message.includes('Failed to fetch dynamically imported module') ||
    error.message.includes('Importing a module script failed') ||
    error.name === 'ChunkLoadError'
}

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)

    if (isChunkLoadError(error)) {
      const alreadyReloaded = sessionStorage.getItem(CHUNK_RELOAD_KEY)
      if (!alreadyReloaded) {
        sessionStorage.setItem(CHUNK_RELOAD_KEY, '1')
        window.location.reload()
      }
    }
  }

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) return this.props.fallback
      const isChunk = isChunkLoadError(this.state.error)
      return (
        <div
          className="min-h-[60vh] flex flex-col items-center justify-center p-6"
          style={{ backgroundColor: 'var(--ms-bg)', color: 'var(--ms-text)' }}
        >
          <h1 className="text-xl font-semibold mb-2">Something went wrong</h1>
          <p className="text-sm mb-3 max-w-md text-center" style={{ color: 'var(--ms-text-mid)' }}>
            {isChunk
              ? 'A new version of the app has been deployed. Please reload to update.'
              : 'An unexpected error occurred. Please try refreshing the page or return to the dashboard.'}
          </p>
          <p className="text-xs mb-6 max-w-md text-center font-mono px-3 py-2 rounded" style={{ color: '#C96A5A', backgroundColor: 'rgba(201,106,90,0.08)', border: '1px solid rgba(201,106,90,0.2)' }}>
            {this.state.error.message}
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-lg font-medium transition-colors"
              style={{ backgroundColor: 'var(--ms-accent)', color: '#FFF8EC' }}
            >
              Reload page
            </button>
            <Link
              to="/dashboard"
              className="px-4 py-2 rounded-lg font-medium border transition-colors"
              style={{ borderColor: 'var(--ms-border)', color: 'var(--ms-text)' }}
            >
              Go to dashboard
            </Link>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
