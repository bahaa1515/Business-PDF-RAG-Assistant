import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import Layout from './Layout'

const logout = vi.fn()
let role = 'user'

vi.mock('../contexts/RoleContext', () => ({
  useRole: () => ({ role, logout })
}))

describe('Layout role visibility', () => {
  beforeEach(() => {
    role = 'user'
    logout.mockClear()
  })

  it('shows only chat navigation for normal users', () => {
    render(<MemoryRouter><Layout><p>Page</p></Layout></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Chat' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Documents' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Failed Questions' })).not.toBeInTheDocument()
  })

  it('shows all admin navigation and logs out', async () => {
    role = 'admin'
    logout.mockResolvedValue()
    render(<MemoryRouter><Layout><p>Page</p></Layout></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Documents' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Evaluation' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Optimization' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Failed Questions' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Logout' }))
    await waitFor(() => expect(logout).toHaveBeenCalledOnce())
  })
})
