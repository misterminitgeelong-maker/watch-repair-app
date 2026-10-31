import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import LoginPage from './LoginPage'

const mocks = vi.hoisted(() => ({
  login: vi.fn(),
  multiSiteLogin: vi.fn(),
  setToken: vi.fn(),
}))
vi.mock('@/lib/api', () => ({
  login: mocks.login,
  multiSiteLogin: mocks.multiSiteLogin,
  getRememberMe: () => false,
  setRememberMe: vi.fn(),
  seedDemoData: vi.fn(),
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}))
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ token: null, sessionReady: true, login: mocks.setToken }),
}))

function renderLogin() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  const response = {
    data: { access_token: 'test-only-token', expires_in_seconds: 900 },
  }
  mocks.login.mockResolvedValue(response)
  mocks.multiSiteLogin.mockResolvedValue(response)
})

describe('simplified login', () => {
  it('uses email login when the optional Shop ID is blank', async () => {
    renderLogin()
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'owner@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password', { exact: true }), {
      target: { value: 'test-only-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^Log in$/ }))
    await waitFor(() =>
      expect(mocks.multiSiteLogin).toHaveBeenCalledWith(
        'owner@example.com',
        'test-only-password',
      ),
    )
    expect(mocks.login).not.toHaveBeenCalled()
  })

  it('uses the existing shop login when a Shop ID is supplied', async () => {
    renderLogin()
    fireEvent.click(screen.getByRole('button', { name: 'Use a Shop ID' }))
    fireEvent.change(screen.getByLabelText(/Shop ID/), {
      target: { value: 'myshop' },
    })
    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'owner@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password', { exact: true }), {
      target: { value: 'test-only-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^Log in$/ }))
    await waitFor(() =>
      expect(mocks.login).toHaveBeenCalledWith(
        'myshop',
        'owner@example.com',
        'test-only-password',
      ),
    )
    expect(mocks.multiSiteLogin).not.toHaveBeenCalled()
  })

  it('reveals the password without submitting the form', () => {
    renderLogin()
    const password = screen.getByLabelText('Password', { exact: true })
    expect(password).toHaveAttribute('type', 'password')
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }))
    expect(password).toHaveAttribute('type', 'text')
    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }))
    expect(password).toHaveAttribute('type', 'password')
    expect(mocks.login).not.toHaveBeenCalled()
    expect(mocks.multiSiteLogin).not.toHaveBeenCalled()
  })
})

