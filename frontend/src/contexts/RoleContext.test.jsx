import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { RoleProvider, useRole } from './RoleContext'
import * as api from '../api/client'

vi.mock('../api/client', () => ({
  getSession: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  setCsrfToken: vi.fn()
}))

function Harness() {
  const { role, loading, login, logout } = useRole()
  return (
    <div>
      <span>{loading ? 'loading' : role || 'anonymous'}</span>
      <button onClick={() => login('admin', 'secret')}>Login</button>
      <button onClick={logout}>Logout</button>
    </div>
  )
}

describe('RoleProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.clearAllMocks()
  })

  it('restores an existing session', async () => {
    api.getSession.mockResolvedValue({ data: { role: 'admin', csrf_token: 'csrf-restored' } })
    render(<RoleProvider><Harness /></RoleProvider>)
    await waitFor(() => expect(screen.getByText('admin')).toBeInTheDocument())
    expect(api.setCsrfToken).toHaveBeenCalledWith('csrf-restored')
  })

  it('logs in without storing a browser token and logs out', async () => {
    window.localStorage.setItem('docuquery_legal_acceptance', 'keep-after-logout')
    api.getSession.mockRejectedValue(new Error('no session'))
    api.login.mockResolvedValue({ data: { role: 'admin', csrf_token: 'csrf-login' } })
    api.logout.mockResolvedValue({})
    render(<RoleProvider><Harness /></RoleProvider>)
    await waitFor(() => expect(screen.getByText('anonymous')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Login' }))
    await waitFor(() => expect(screen.getByText('admin')).toBeInTheDocument())
    expect(api.setCsrfToken).toHaveBeenCalledWith('csrf-login')
    expect(window.localStorage.getItem('docuquery_token')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Logout' }))
    await waitFor(() => expect(screen.getByText('anonymous')).toBeInTheDocument())
    expect(api.logout).toHaveBeenCalledOnce()
    expect(window.localStorage.getItem('docuquery_token')).toBeNull()
    expect(window.localStorage.getItem('docuquery_legal_acceptance')).toBe('keep-after-logout')
  })
})
