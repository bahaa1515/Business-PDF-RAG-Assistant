import React from 'react'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

let auth = { role: null, loading: false }

vi.mock('./contexts/RoleContext', () => ({
  RoleProvider: ({ children }) => children,
  useRole: () => auth
}))
vi.mock('./components/Layout', () => ({ default: ({ children }) => <div>Layout {children}</div> }))
vi.mock('./components/LegalAcceptanceGate', () => ({ default: ({ children }) => children }))
vi.mock('./pages/ChatPage', () => ({ default: () => <div>Chat Page</div> }))
vi.mock('./pages/DocumentsPage', () => ({ default: () => <div>Documents Page</div> }))
vi.mock('./pages/EvaluationPage', () => ({ default: () => <div>Evaluation Page</div> }))
vi.mock('./pages/OptimizationPage', () => ({ default: () => <div>Optimization Page</div> }))
vi.mock('./pages/AnalyticsPage', () => ({ default: () => <div>Analytics Page</div> }))
vi.mock('./pages/AISettingsPage', () => ({ default: () => <div>AI Settings Page</div> }))
vi.mock('./pages/LoginPage', () => ({ default: () => <div>Login Page</div> }))

describe('App route guards', () => {
  beforeEach(() => {
    auth = { role: null, loading: false }
    window.history.pushState({}, '', '/')
  })

  it('redirects anonymous visitors to login', () => {
    render(<App />)
    expect(screen.getByText('Login Page')).toBeInTheDocument()
  })

  it('blocks normal users from admin routes', () => {
    auth = { role: 'user', loading: false }
    window.history.pushState({}, '', '/analytics')
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Unauthorized' })).toBeInTheDocument()
  })

  it('allows admins to open analytics', () => {
    auth = { role: 'admin', loading: false }
    window.history.pushState({}, '', '/analytics')
    render(<App />)
    expect(screen.getByText('Analytics Page')).toBeInTheDocument()
  })

  it('allows only admins to open AI settings', () => {
    auth = { role: 'user', loading: false }
    window.history.pushState({}, '', '/ai-settings')
    const rendered = render(<App />)
    expect(screen.getByRole('heading', { name: 'Unauthorized' })).toBeInTheDocument()
    rendered.unmount()

    auth = { role: 'admin', loading: false }
    window.history.pushState({}, '', '/ai-settings')
    render(<App />)
    expect(screen.getByText('AI Settings Page')).toBeInTheDocument()
  })
})
