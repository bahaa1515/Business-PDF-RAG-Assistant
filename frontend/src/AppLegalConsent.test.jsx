import React from 'react'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import {
  LEGAL_ACCEPTANCE_STORAGE_KEY,
  PRIVACY_VERSION,
  TERMS_VERSION
} from './legal/storage'

let auth = { role: 'user', loading: false }

vi.mock('./contexts/RoleContext', () => ({
  RoleProvider: ({ children }) => children,
  useRole: () => auth
}))
vi.mock('./contexts/ConsentContext', () => ({
  ConsentProvider: ({ children }) => children,
  useConsent: () => ({ openPreferences: vi.fn() })
}))
vi.mock('./components/CookieConsentManager', () => ({ default: () => null }))
vi.mock('./components/Layout', () => ({ default: ({ children }) => <div>Layout {children}</div> }))
vi.mock('./pages/ChatPage', () => ({ default: () => <div>Chat Page</div> }))
vi.mock('./pages/DocumentsPage', () => ({ default: () => <div>Documents Page</div> }))
vi.mock('./pages/EvaluationPage', () => ({ default: () => <div>Evaluation Page</div> }))
vi.mock('./pages/OptimizationPage', () => ({ default: () => <div>Optimization Page</div> }))
vi.mock('./pages/AnalyticsPage', () => ({ default: () => <div>Analytics Page</div> }))
vi.mock('./pages/LoginPage', () => ({ default: () => <div>Login Page</div> }))

describe('App legal acceptance routes', () => {
  beforeEach(() => {
    auth = { role: 'user', loading: false }
    window.localStorage.clear()
    window.history.pushState({}, '', '/chat')
  })

  it('blocks first-time users from the application', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Before you continue' })).toBeInTheDocument()
    expect(screen.queryByText('Chat Page')).not.toBeInTheDocument()
  })

  it('blocks first-time admins from admin features', () => {
    auth = { role: 'admin', loading: false }
    window.history.pushState({}, '', '/documents')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Before you continue' })).toBeInTheDocument()
    expect(screen.queryByText('Documents Page')).not.toBeInTheDocument()
  })

  it('allows the application after current legal versions are accepted', () => {
    window.localStorage.setItem(LEGAL_ACCEPTANCE_STORAGE_KEY, JSON.stringify({
      termsVersion: TERMS_VERSION,
      privacyVersion: PRIVACY_VERSION,
      acceptedAt: new Date().toISOString()
    }))
    render(<App />)
    expect(screen.getByText('Chat Page')).toBeInTheDocument()
  })

  it('keeps legal pages public before login or acceptance', () => {
    auth = { role: null, loading: false }
    window.history.pushState({}, '', '/terms')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Terms of Service' })).toBeInTheDocument()
  })
})
