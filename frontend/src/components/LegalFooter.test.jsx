import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import LegalFooter from './LegalFooter'

describe('LegalFooter', () => {
  it('provides legal links and opens cookie preferences', () => {
    const onManagePreferences = vi.fn()
    render(
      <MemoryRouter>
        <LegalFooter onManagePreferences={onManagePreferences} />
      </MemoryRouter>
    )

    expect(screen.getByRole('link', { name: 'Terms of Service' })).toHaveAttribute('href', '/terms')
    expect(screen.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute('href', '/privacy')
    expect(screen.getByRole('link', { name: 'Cookie/Storage Policy' })).toHaveAttribute('href', '/cookie-policy')
    fireEvent.click(screen.getByRole('button', { name: 'Manage Cookie Preferences' }))
    expect(onManagePreferences).toHaveBeenCalledOnce()
  })
})
