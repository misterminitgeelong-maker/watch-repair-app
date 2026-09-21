import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

// Shared with the lazy-route loader, which catches this failure first. Two
// separate keys meant one stale tab could reload twice.
import { CHUNK_RELOAD_KEY } from '@/lib/routePrefetch'

function isChunkLoadError(error: Error): boolean {
  return error.message.includes('Failed to fetch dynamically imported module') ||
    error.message.includes('Importing a module script failed') ||
    error.name === 'ChunkLoadError'
}

interface Props {
  children: ReactNode
  fallback?: ReactNode
  /** Change this to clear a caught error — typically the current pathname.
   * Without it a boundary whose `key` is deliberately stable (so the shell
   * does not remount on every navigation) stays stuck on the fallback for the
   * rest of the session, including for the fallback's own "go to dashboard"
   * link, which navigates underneath an error screen that never goes away. */
  resetKey?: string
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

  componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: null })
    }
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
          <p className="text-xs mb-6 max-w-md text-center font-mono px-3 py-2 rounded" style={{ color: 'var(--ms-error)', backgroundColor: 'color-mix(in srgb, var(--ms-error) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--ms-error) 20%, transparent)' }}>
            {this.state.error.message}
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="min-h-11 rounded-lg px-4 py-2 font-medium transition-colors"
              style={{ backgroundColor: 'var(--ms-accent)', color: '#FFF8EC' }}
            >
              Reload page
            </button>
            <Link
              to="/dashboard"
              className="inline-flex min-h-11 items-center rounded-lg border px-4 py-2 font-medium transition-colors"
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
