import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

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
  }

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) return this.props.fallback
      return (
        <div
          className="min-h-[60vh] flex flex-col items-center justify-center p-6"
          style={{ backgroundColor: 'var(--cafe-bg)', color: 'var(--cafe-text)' }}
        >
          <h1 className="text-xl font-semibold mb-2">Something went wrong</h1>
          <p className="text-sm mb-6 max-w-md text-center" style={{ color: 'var(--cafe-text-mid)' }}>
            An unexpected error occurred. Please try refreshing the page or return to the dashboard.
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-lg font-medium transition-colors"
              style={{ backgroundColor: 'var(--cafe-amber)', color: '#FFF8EC' }}
            >
              Reload page
            </button>
            <Link
              to="/dashboard"
              className="px-4 py-2 rounded-lg font-medium border transition-colors"
              style={{ borderColor: 'var(--cafe-border)', color: 'var(--cafe-text)' }}
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
