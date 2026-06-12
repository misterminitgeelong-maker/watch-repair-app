import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { FeatureGate } from './FeatureGate'

// Mock useAuth so each test drives the gate with an explicit auth shape.
const mockAuth = vi.fn()
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => mockAuth(),
}))

type AuthShape = {
  role?: string | null
  enabledFeatures?: string[]
  featuresKnown?: boolean
  planCode?: string
  product?: string
  tenantSlug?: string | null
}

function setAuth(partial: AuthShape) {
  const enabled = partial.enabledFeatures ?? []
  mockAuth.mockReturnValue({
    role: partial.role ?? 'owner',
    product: partial.product ?? 'mainspring',
    planCode: partial.planCode ?? 'pro',
    tenantSlug: partial.tenantSlug ?? 'timekeepers',
    featuresKnown: partial.featuresKnown ?? false,
    hasFeature: (f: string) => enabled.includes(f),
  })
}

function renderGate(startPath = '/jobs/123') {
  return render(
    <MemoryRouter initialEntries={[startPath]}>
      <Routes>
        <Route
          path="/jobs/:id"
          element={
            <FeatureGate feature="watch">
              <div>JOB CONTENT</div>
            </FeatureGate>
          }
        />
        <Route path="/dashboard" element={<div>DASHBOARD</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('FeatureGate', () => {
  beforeEach(() => mockAuth.mockReset())

  it('renders children when the feature is enabled', () => {
    setAuth({ enabledFeatures: ['watch'], featuresKnown: true })
    renderGate()
    expect(screen.getByText('JOB CONTENT')).toBeInTheDocument()
  })

  it('renders children for platform_admin regardless of features', () => {
    setAuth({ role: 'platform_admin', enabledFeatures: [], featuresKnown: true })
    renderGate()
    expect(screen.getByText('JOB CONTENT')).toBeInTheDocument()
  })

  it('shows a spinner (does NOT redirect) while features are still unknown', () => {
    // Regression: a scanned ticket QR deep-link used to bounce to the dashboard
    // because the gate evaluated before /auth/session populated features.
    setAuth({ enabledFeatures: [], featuresKnown: false })
    renderGate()
    expect(screen.queryByText('DASHBOARD')).not.toBeInTheDocument()
    expect(screen.queryByText('JOB CONTENT')).not.toBeInTheDocument()
  })

  it('redirects to the dashboard once features are known and the feature is absent', () => {
    setAuth({ enabledFeatures: ['shoe'], featuresKnown: true })
    renderGate()
    expect(screen.getByText('DASHBOARD')).toBeInTheDocument()
    expect(screen.queryByText('JOB CONTENT')).not.toBeInTheDocument()
  })

  it('shows an on-plan message instead of looping when already on the fallback path', () => {
    setAuth({ enabledFeatures: [], featuresKnown: true })
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route
            path="/dashboard"
            element={
              <FeatureGate feature="watch">
                <div>JOB CONTENT</div>
              </FeatureGate>
            }
          />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText(/not available on your plan/i)).toBeInTheDocument()
  })
})
