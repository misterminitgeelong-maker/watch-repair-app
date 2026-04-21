import { describe, expect, it } from 'vitest'
import { render, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useEffect, useRef } from 'react'

import { AuthProvider, useAuth } from './AuthContext'

// Keep refs to the action identities we observed across renders so the test
// can assert they're stable (F-M1: useCallback + latest-ref memoization).
function IdentityProbe({
  onCapture,
}: {
  onCapture: (snapshot: {
    login: unknown
    logout: unknown
    refreshSession: unknown
    switchSite: unknown
    hasFeature: unknown
  }) => void
}) {
  const auth = useAuth()
  const renderCountRef = useRef(0)
  useEffect(() => {
    renderCountRef.current += 1
    onCapture({
      login: auth.login,
      logout: auth.logout,
      refreshSession: auth.refreshSession,
      switchSite: auth.switchSite,
      hasFeature: auth.hasFeature,
    })
  })
  return <span data-testid="probe">{renderCountRef.current}</span>
}

describe('<AuthProvider /> (F-M1 memoization regression)', () => {
  it('action identities are stable across re-renders', () => {
    const snapshots: Array<Record<string, unknown>> = []
    const { rerender } = render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <IdentityProbe onCapture={(s) => snapshots.push(s)} />
        </AuthProvider>
      </MemoryRouter>,
    )
    // Force additional renders.
    act(() => {
      rerender(
        <MemoryRouter initialEntries={['/']}>
          <AuthProvider>
            <IdentityProbe onCapture={(s) => snapshots.push(s)} />
          </AuthProvider>
        </MemoryRouter>,
      )
    })

    expect(snapshots.length).toBeGreaterThanOrEqual(2)
    const first = snapshots[0]
    const last = snapshots[snapshots.length - 1]
    // Each of the five action functions must have the same reference identity
    // across renders — that's what prevents the useAuth() fan-out re-render
    // problem that F-M1 fixed.
    for (const key of ['login', 'logout', 'refreshSession', 'switchSite', 'hasFeature']) {
      expect(last[key]).toBe(first[key])
    }
  })
})
