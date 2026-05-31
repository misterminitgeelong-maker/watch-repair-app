import { describe, it, expect, beforeAll, afterAll, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import api, { getStoredAccessToken, type AuthSession } from '@/lib/api'
import { testServer } from '@/test/msw/server'
import { AuthProvider, useAuth } from './AuthContext'

function makeJwt(role = 'owner', expSecondsFromNow = 3600): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const payload = btoa(
    JSON.stringify({ sub: `t1:u1:${role}`, exp: Math.floor(Date.now() / 1000) + expSecondsFromNow }),
  )
  return `${header}.${payload}.signature`
}

const TEST_JWT = makeJwt('owner')

function sessionResponse(): AuthSession {
  return {
    user: { id: 'u1', tenant_id: 't1', email: 'owner@example.test', full_name: 'Owner', role: 'owner', is_active: true },
    tenant_id: 't1',
    tenant_slug: 'timekeepers',
    plan_code: 'pro',
    enabled_features: ['watch'],
    active_site_tenant_id: 't1',
    available_sites: [],
  }
}

function Consumer() {
  const { token, role, login, logout } = useAuth()
  return (
    <div>
      <div data-testid="token">{token ?? 'none'}</div>
      <div data-testid="role">{role ?? 'none'}</div>
      <button onClick={() => login(TEST_JWT, 'refresh-1', 3600)}>do-login</button>
      <button onClick={() => logout()}>do-logout</button>
    </div>
  )
}

function renderAuth() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('AuthContext', () => {
  const previousApiBase = api.defaults.baseURL

  beforeAll(() => {
    api.defaults.baseURL = 'http://127.0.0.1/v1'
  })

  afterAll(() => {
    api.defaults.baseURL = previousApiBase
  })

  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    testServer.use(http.get('*/v1/auth/session', () => HttpResponse.json(sessionResponse())))
  })

  afterEach(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  it('starts unauthenticated when no token is stored', () => {
    renderAuth()
    expect(screen.getByTestId('token').textContent).toBe('none')
    expect(getStoredAccessToken()).toBeNull()
  })

  it('login stores the token and exposes role, session loads user role', async () => {
    renderAuth()
    await userEvent.click(screen.getByText('do-login'))

    expect(getStoredAccessToken()).toBe(TEST_JWT)
    expect(screen.getByTestId('token').textContent).toBe(TEST_JWT)
    // Role parsed optimistically from the JWT sub claim.
    expect(screen.getByTestId('role').textContent).toBe('owner')

    // /auth/session resolves and confirms the role.
    await waitFor(() => expect(screen.getByTestId('role').textContent).toBe('owner'))
  })

  it('logout clears the stored token and resets context', async () => {
    renderAuth()
    await userEvent.click(screen.getByText('do-login'))
    expect(getStoredAccessToken()).toBe(TEST_JWT)

    await userEvent.click(screen.getByText('do-logout'))

    expect(getStoredAccessToken()).toBeNull()
    expect(screen.getByTestId('token').textContent).toBe('none')
    expect(screen.getByTestId('role').textContent).toBe('none')
  })
})
