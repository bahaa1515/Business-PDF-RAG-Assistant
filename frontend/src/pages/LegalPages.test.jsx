import React from 'react'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import TermsPage from './TermsPage'
import PrivacyPage from './PrivacyPage'
import CookiePolicyPage from './CookiePolicyPage'

describe('Legal pages', () => {
  it('renders Terms of Service', () => {
    render(<MemoryRouter><TermsPage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Terms of Service' })).toBeInTheDocument()
  })

  it('renders Privacy Policy', () => {
    render(<MemoryRouter><PrivacyPage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Privacy Policy' })).toBeInTheDocument()
  })

  it('renders Cookie and Storage Policy', () => {
    render(<MemoryRouter><CookiePolicyPage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Cookie and Storage Policy' })).toBeInTheDocument()
    expect(screen.getByText(/localStorage/i)).toBeInTheDocument()
  })
})
