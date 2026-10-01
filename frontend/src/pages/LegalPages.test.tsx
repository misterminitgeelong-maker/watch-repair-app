import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AccountDeletionPage, PrivacyPolicyPage } from './LegalPages'

describe('legal pages', () => {
  it('privacy policy names the company and contact address', () => {
    render(<PrivacyPolicyPage />)
    expect(screen.getByRole('heading', { name: 'Privacy Policy' })).toBeInTheDocument()
    expect(screen.getAllByText(/Unamigo Pty Ltd/).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: 'admin@mainspring.au' }).length).toBeGreaterThan(0)
  })

  it('account deletion page explains how to ask', () => {
    render(<AccountDeletionPage />)
    expect(screen.getByRole('heading', { name: 'Delete your Mainspring account' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'admin@mainspring.au' })).toHaveAttribute('href', expect.stringContaining('mailto:admin@mainspring.au'))
  })
})
