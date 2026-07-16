import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import LoginPage from './LoginPage'

const login = vi.fn()

vi.mock('../contexts/RoleContext', () => ({
  useRole: () => ({ login })
}))

describe('LoginPage', () => {
  beforeEach(() => login.mockReset())

  it('logs in as a normal user without a password', async () => {
    login.mockResolvedValue()
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: 'Continue as User' }))
    await waitFor(() => expect(login).toHaveBeenCalledWith('user', ''))
  })

  it('requires and submits the admin password', async () => {
    login.mockResolvedValue()
    render(<MemoryRouter><LoginPage /></MemoryRouter>)
    const adminButton = screen.getByRole('button', { name: 'Continue as Admin' })
    expect(adminButton).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Admin password'), { target: { value: 'secret' } })
    fireEvent.click(adminButton)
    await waitFor(() => expect(login).toHaveBeenCalledWith('admin', 'secret'))
  })
})
