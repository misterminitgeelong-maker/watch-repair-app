/**
 * Tests for the shared "enter shop" impersonation mechanism.
 *
 * Two roles now borrow a shop session — platform admin, and a Minit
 * administrator entering a shop in their own network. They share storage keys,
 * so the interesting behaviour is bookkeeping: what is saved to get back, what
 * the banner says, where Return goes, and what happens to a response that
 * carries no refresh token.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const navigate = vi.fn()
const authLogin = vi.fn()
const refreshSession = vi.fn(async () => {})
const platformAdminEnterShop = vi.fn()
const minitHqEnterShop = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigate }
})
vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ login: authLogin, refreshSession }),
}))
vi.mock('@/lib/api', () => ({
  platformAdminEnterShop: (id: string) => platformAdminEnterShop(id),
  minitHqEnterShop: (id: string) => minitHqEnterShop(id),
}))

const { AdminReturnBanner, useAdminEnterShop, useMinitHqEnterShop } = await import(
  './adminImpersonation'
)

/** The HQ endpoint issues no refresh token: the window is the whole window. */
function hqResponse() {
  return {
    data: {
      access_token: 'shop-token',
      refresh_token: '',
      expires_in_seconds: 1800,
      tenant_id: 't-1',
      tenant_name: 'Shop A',
      tenant_slug: 'minit-8001',
    },
  }
}

function EnterButton({ hq }: { hq: boolean }) {
  // Hooks cannot be called conditionally, so call both and pick.
  const admin = useAdminEnterShop()
  const minit = useMinitHqEnterShop()
  const { enterShop, error } = hq ? minit : admin
  return (
    <>
      <button onClick={() => void enterShop('t-1')}>enter</button>
      {error && <span role="alert">{error}</span>}
    </>
  )
}

function renderEnter(hq: boolean) {
  return render(
    <MemoryRouter>
      <EnterButton hq={hq} />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  sessionStorage.clear()
  localStorage.clear()
  vi.clearAllMocks()
  minitHqEnterShop.mockResolvedValue(hqResponse())
  platformAdminEnterShop.mockResolvedValue({
    data: { access_token: 'admin-shop-token', refresh_token: 'r-1', expires_in_seconds: 900 },
  })
})
afterEach(() => vi.clearAllMocks())

describe('Minit HQ enter shop', () => {
  it('calls the parent-account endpoint, not the platform-admin one', async () => {
    renderEnter(true)
    await userEvent.click(screen.getByText('enter'))

    await waitFor(() => expect(minitHqEnterShop).toHaveBeenCalledWith('t-1'))
    expect(platformAdminEnterShop).not.toHaveBeenCalled()
  })

  it('stores an absent refresh token as null rather than an empty string', async () => {
    // Stored as '', the refresh path would later try to redeem an empty token.
    renderEnter(true)
    await userEvent.click(screen.getByText('enter'))

    await waitFor(() => expect(authLogin).toHaveBeenCalled())
    expect(authLogin).toHaveBeenCalledWith('shop-token', null, 1800)
  })

  it('saves the HQ tokens so the session can be handed back', async () => {
    localStorage.setItem('token', 'hq-token')
    localStorage.setItem('refresh_token', 'hq-refresh')
    renderEnter(true)
    await userEvent.click(screen.getByText('enter'))

    await waitFor(() => expect(authLogin).toHaveBeenCalled())
    expect(sessionStorage.getItem('admin_prev_token')).toBe('hq-token')
    expect(sessionStorage.getItem('admin_prev_refresh_token')).toBe('hq-refresh')
  })

  it('does not strand a half-set impersonation when the call fails', async () => {
    localStorage.setItem('token', 'hq-token')
    minitHqEnterShop.mockRejectedValue(new Error('403'))
    renderEnter(true)
    await userEvent.click(screen.getByText('enter'))

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    // A saved prev-token with no session borrowed would show the banner forever.
    expect(sessionStorage.getItem('admin_prev_token')).toBeNull()
  })
})

describe('AdminReturnBanner', () => {
  function renderBanner() {
    return render(
      <MemoryRouter>
        <AdminReturnBanner />
      </MemoryRouter>,
    )
  }

  it('shows nothing when no session has been borrowed', () => {
    const { container } = renderBanner()
    expect(container).toBeEmptyDOMElement()
  })

  it('names the role that is being worn', async () => {
    // The banner keys off a saved previous token, so there has to be one.
    localStorage.setItem('token', 'hq-token')
    renderEnter(true)
    await userEvent.click(screen.getByText('enter'))
    await waitFor(() => expect(authLogin).toHaveBeenCalled())

    const { container } = renderBanner()
    // The label sits between two text nodes, so match on the whole banner.
    expect(container.textContent).toContain('Viewing as Minit Administrator')
  })

  it('still says Platform Admin for the platform-admin route', async () => {
    localStorage.setItem('token', 'admin-token')
    renderEnter(false)
    await userEvent.click(screen.getByText('enter'))
    await waitFor(() => expect(authLogin).toHaveBeenCalled())

    const { container } = renderBanner()
    expect(container.textContent).toContain('Viewing as Platform Admin')
  })

  it('returns a Minit administrator to the shops page, not to platform admin', async () => {
    localStorage.setItem('token', 'hq-token')
    renderEnter(true)
    await userEvent.click(screen.getByText('enter'))
    await waitFor(() => expect(authLogin).toHaveBeenCalled())

    renderBanner()
    await userEvent.click(screen.getByText('Return'))

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/minit/shops'))
    expect(authLogin).toHaveBeenLastCalledWith('hq-token', null)
  })

  it('clears its bookkeeping on return so the banner does not come back', async () => {
    localStorage.setItem('token', 'hq-token')
    renderEnter(true)
    await userEvent.click(screen.getByText('enter'))
    await waitFor(() => expect(authLogin).toHaveBeenCalled())

    renderBanner()
    await userEvent.click(screen.getByText('Return'))

    await waitFor(() => expect(sessionStorage.getItem('admin_prev_token')).toBeNull())
    expect(sessionStorage.getItem('admin_impersonation_label')).toBeNull()
    expect(sessionStorage.getItem('admin_impersonation_return_path')).toBeNull()
  })
})
