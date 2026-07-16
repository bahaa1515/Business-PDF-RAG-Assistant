import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import LegalAcceptanceGate from './LegalAcceptanceGate'
import {
  LEGAL_ACCEPTANCE_STORAGE_KEY,
  PRIVACY_VERSION,
  TERMS_VERSION,
  hasCurrentLegalAcceptance
} from '../legal/storage'

describe('LegalAcceptanceGate', () => {
  beforeEach(() => window.localStorage.clear())

  function renderGate() {
    return render(
      <MemoryRouter>
        <LegalAcceptanceGate><div>Protected application</div></LegalAcceptanceGate>
      </MemoryRouter>
    )
  }

  it('blocks first-time users until terms and privacy are accepted', () => {
    renderGate()
    expect(screen.getByRole('heading', { name: 'Before you continue' })).toBeInTheDocument()
    expect(screen.queryByText('Protected application')).not.toBeInTheDocument()

    const continueButton = screen.getByRole('button', { name: 'Accept and continue' })
    expect(continueButton).toBeDisabled()
    fireEvent.click(screen.getByLabelText('I accept the Terms of Service'))
    fireEvent.click(screen.getByLabelText('I acknowledge the Privacy Policy'))
    fireEvent.click(continueButton)

    expect(screen.getByText('Protected application')).toBeInTheDocument()
    const acceptance = JSON.parse(window.localStorage.getItem(LEGAL_ACCEPTANCE_STORAGE_KEY))
    expect(acceptance.termsVersion).toBe(TERMS_VERSION)
    expect(acceptance.privacyVersion).toBe(PRIVACY_VERSION)
    expect(acceptance.acceptedAt).toBeTruthy()
  })

  it('remembers acceptance after refresh and asks again after a version change', () => {
    window.localStorage.setItem(LEGAL_ACCEPTANCE_STORAGE_KEY, JSON.stringify({
      termsVersion: TERMS_VERSION,
      privacyVersion: PRIVACY_VERSION,
      acceptedAt: new Date().toISOString()
    }))
    renderGate()
    expect(screen.getByText('Protected application')).toBeInTheDocument()
    expect(hasCurrentLegalAcceptance()).toBe(true)
    expect(hasCurrentLegalAcceptance({ termsVersion: 'future-terms-version' })).toBe(false)
  })

  it('asks again when browser storage is cleared', () => {
    window.localStorage.setItem(LEGAL_ACCEPTANCE_STORAGE_KEY, JSON.stringify({
      termsVersion: TERMS_VERSION,
      privacyVersion: PRIVACY_VERSION,
      acceptedAt: new Date().toISOString()
    }))
    const view = renderGate()
    expect(screen.getByText('Protected application')).toBeInTheDocument()

    window.localStorage.clear()
    view.unmount()
    renderGate()
    expect(screen.getByRole('heading', { name: 'Before you continue' })).toBeInTheDocument()
  })
})
